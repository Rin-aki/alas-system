package com.alas.system.repository;

import com.alas.system.domain.Announcement;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AnnouncementRepository extends JpaRepository<Announcement, Integer> {

    Optional<Announcement> findFirstByIsActiveTrueOrderByCreatedAtDesc();
}
