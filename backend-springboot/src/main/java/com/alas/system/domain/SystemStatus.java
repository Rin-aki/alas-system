package com.alas.system.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "system_status")
public class SystemStatus {

    @Id
    private Integer id;

    @Column(name = "is_maintenance")
    private Boolean isMaintenance;

    @Column(name = "maintenance_message")
    private String maintenanceMessage;

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }

    public Boolean getIsMaintenance() {
        return isMaintenance;
    }

    public void setIsMaintenance(Boolean maintenance) {
        isMaintenance = maintenance;
    }

    public String getMaintenanceMessage() {
        return maintenanceMessage;
    }

    public void setMaintenanceMessage(String maintenanceMessage) {
        this.maintenanceMessage = maintenanceMessage;
    }
}
