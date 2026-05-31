package com.alas.system.service;

import com.alas.system.domain.StripeOrder;
import com.alas.system.domain.User;
import com.alas.system.repository.StripeOrderRepository;
import com.alas.system.repository.UserRepository;
import com.stripe.Stripe;
import com.stripe.exception.SignatureVerificationException;
import com.stripe.exception.StripeException;
import com.stripe.model.Event;
import com.stripe.model.checkout.Session;
import com.stripe.net.Webhook;
import com.stripe.param.checkout.SessionCreateParams;
import jakarta.annotation.PostConstruct;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);

    record Plan(String id, int days, long amount, String label) {}

    private static final List<Plan> PLANS = List.of(
            new Plan("plan_30d",  30,  3800L,  "30天套餐"),
            new Plan("plan_90d",  90,  11000L, "90天套餐"),
            new Plan("plan_180d", 180, 21500L, "180天套餐"),
            new Plan("plan_365d", 365, 41800L, "365天套餐")
    );

    @Value("${stripe.secret-key}")
    private String secretKey;

    @Value("${stripe.webhook-secret}")
    private String webhookSecret;

    // Frontend URL used to build success/cancel redirect URLs
    @Value("${app.frontend-url:https://alasm.gjiang.xyz:58000}")
    private String frontendUrl;

    private final StripeOrderRepository orderRepository;
    private final UserRepository userRepository;

    public PaymentService(StripeOrderRepository orderRepository, UserRepository userRepository) {
        this.orderRepository = orderRepository;
        this.userRepository = userRepository;
    }

    @PostConstruct
    public void init() {
        Stripe.apiKey = secretKey;
    }

    public List<Map<String, Object>> listPlans() {
        return PLANS.stream().map(p -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("id", p.id());
            m.put("days", p.days());
            m.put("amount", p.amount());
            m.put("label", p.label());
            return m;
        }).toList();
    }

    @Transactional
    public Map<String, Object> createCheckoutSession(User user, String planId) {
        Plan plan = PLANS.stream()
                .filter(p -> p.id().equals(planId))
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "无效的套餐ID"));

        try {
            SessionCreateParams params = SessionCreateParams.builder()
                    .setMode(SessionCreateParams.Mode.PAYMENT)
                    .setCurrency("cny")
                    .addLineItem(SessionCreateParams.LineItem.builder()
                            .setQuantity(1L)
                            .setPriceData(SessionCreateParams.LineItem.PriceData.builder()
                                    .setCurrency("cny")
                                    .setUnitAmount(plan.amount())
                                    .setProductData(SessionCreateParams.LineItem.PriceData.ProductData.builder()
                                            .setName(plan.label())
                                            .setDescription("ALAS 服务 " + plan.days() + " 天使用权限")
                                            .build())
                                    .build())
                            .build())
                    .setSuccessUrl(frontendUrl + "/checkout/success?session_id={CHECKOUT_SESSION_ID}")
                    .setCancelUrl(frontendUrl + "/checkout")
                    .putMetadata("user_id", user.getId().toString())
                    .putMetadata("plan_id", planId)
                    .putMetadata("days", String.valueOf(plan.days()))
                    .build();

            Session session = Session.create(params);

            StripeOrder order = new StripeOrder();
            order.setUserId(user.getId());
            order.setSessionId(session.getId());
            order.setPlanId(planId);
            order.setDays(plan.days());
            order.setAmount((int) plan.amount());
            order.setStatus("pending");
            order.setCreatedAt(LocalDateTime.now());
            orderRepository.save(order);

            Map<String, Object> result = new LinkedHashMap<>();
            result.put("url", session.getUrl());
            result.put("session_id", session.getId());
            return result;

        } catch (StripeException e) {
            log.error("创建 Stripe Checkout Session 失败: {}", e.getMessage());
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "支付服务暂时不可用，请稍后重试");
        }
    }

    @Transactional
    public void handleWebhook(String payload, String sigHeader) {
        Event event;
        try {
            event = Webhook.constructEvent(payload, sigHeader, webhookSecret);
        } catch (SignatureVerificationException e) {
            log.warn("Stripe webhook 签名验证失败");
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid signature");
        }

        if ("checkout.session.completed".equals(event.getType())) {
            Session session = (Session) event.getDataObjectDeserializer()
                    .getObject()
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "无法解析 Stripe event"));
            fulfillOrder(session);
        } else if ("checkout.session.expired".equals(event.getType())) {
            event.getDataObjectDeserializer().getObject().ifPresent(obj -> {
                Session session = (Session) obj;
                orderRepository.findBySessionId(session.getId()).ifPresent(order -> {
                    if ("pending".equals(order.getStatus())) {
                        order.setStatus("expired");
                        orderRepository.save(order);
                        log.info("Stripe Session 已过期，订单标记为 expired: {}", session.getId());
                    }
                });
            });
        }
    }

    private void fulfillOrder(Session session) {
        Optional<StripeOrder> maybeOrder = orderRepository.findBySessionId(session.getId());
        if (maybeOrder.isEmpty()) {
            log.warn("收到未知 session 的 webhook: {}", session.getId());
            return;
        }

        StripeOrder order = maybeOrder.get();
        if ("paid".equals(order.getStatus())) {
            return; // 幂等：已处理过
        }

        order.setStatus("paid");
        order.setPaidAt(LocalDateTime.now());
        orderRepository.save(order);

        userRepository.findById(order.getUserId()).ifPresent(user -> {
            user.setHasPurchased(true);
            LocalDateTime now = LocalDateTime.now();
            LocalDateTime current = user.getPurchaseExpires();
            int days = order.getDays() != null ? order.getDays() : 0;
            if (current != null && current.isAfter(now)) {
                user.setPurchaseExpires(current.plusDays(days));
            } else {
                user.setPurchaseExpires(now.plusDays(days));
            }
            userRepository.save(user);
            log.info("用户 {} 充值成功，套餐 {}，延长 {} 天", user.getId(), order.getPlanId(), order.getDays());
        });
    }

    // Called by the success page to verify the session was actually paid
    public Map<String, Object> verifySession(User user, String sessionId) {
        Optional<StripeOrder> maybeOrder = orderRepository.findBySessionId(sessionId);
        if (maybeOrder.isEmpty() || !maybeOrder.get().getUserId().equals(user.getId())) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "订单不存在");
        }
        StripeOrder order = maybeOrder.get();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("status", order.getStatus());
        result.put("plan_id", order.getPlanId());
        result.put("days", order.getDays());
        result.put("paid", "paid".equals(order.getStatus()));
        return result;
    }
}
