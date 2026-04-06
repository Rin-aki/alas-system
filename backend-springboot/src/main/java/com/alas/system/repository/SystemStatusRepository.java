package com.alas.system.repository;

import com.alas.system.domain.SystemStatus;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SystemStatusRepository extends JpaRepository<SystemStatus, Integer> {
}
