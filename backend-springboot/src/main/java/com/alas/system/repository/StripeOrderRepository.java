package com.alas.system.repository;

import com.alas.system.domain.StripeOrder;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface StripeOrderRepository extends JpaRepository<StripeOrder, Long> {
    Optional<StripeOrder> findBySessionId(String sessionId);
}
