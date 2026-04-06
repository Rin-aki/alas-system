package com.alas.system.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

@Entity
@Table(name = "user")
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(nullable = false, unique = true, length = 120)
    private String email;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Column(name = "is_active")
    private Boolean isActive;

    @Column(name = "has_purchased")
    private Boolean hasPurchased;

    @Column(name = "purchase_expires")
    private LocalDateTime purchaseExpires;

    @Column(name = "alas_ip")
    private Integer alasIp;

    @Column(name = "blhx_ip")
    private Integer blhxIp;

    @Column(name = "ws_ip")
    private Integer wsIp;

    @Column(name = "server_ip")
    private Integer serverIp;

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public Boolean getIsActive() {
        return isActive;
    }

    public void setIsActive(Boolean active) {
        isActive = active;
    }

    public Boolean getHasPurchased() {
        return hasPurchased;
    }

    public void setHasPurchased(Boolean hasPurchased) {
        this.hasPurchased = hasPurchased;
    }

    public LocalDateTime getPurchaseExpires() {
        return purchaseExpires;
    }

    public void setPurchaseExpires(LocalDateTime purchaseExpires) {
        this.purchaseExpires = purchaseExpires;
    }

    public Integer getAlasIp() {
        return alasIp;
    }

    public void setAlasIp(Integer alasIp) {
        this.alasIp = alasIp;
    }

    public Integer getBlhxIp() {
        return blhxIp;
    }

    public void setBlhxIp(Integer blhxIp) {
        this.blhxIp = blhxIp;
    }

    public Integer getWsIp() {
        return wsIp;
    }

    public void setWsIp(Integer wsIp) {
        this.wsIp = wsIp;
    }

    public Integer getServerIp() {
        return serverIp;
    }

    public void setServerIp(Integer serverIp) {
        this.serverIp = serverIp;
    }
}
