"""
app/accounts/crm/campaigns/model.py

SQLAlchemy Models for CRM Campaigns, Trigger Event Logs
and Customer Assigned Offers.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from sqlalchemy.orm import relationship

from app.db.base import Base


class Campaign(Base):
    __tablename__ = "crm_campaigns"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)

    campaign_type = Column(
        String(100),
        nullable=False,
    )

    message_template = Column(
        Text,
        nullable=False,
    )

    channel = Column(
        String(50),
        default="WHATSAPP",
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class CampaignLog(Base):
    __tablename__ = "crm_campaign_logs"

    id = Column(Integer, primary_key=True, index=True)

    campaign_id = Column(
        Integer,
        ForeignKey("crm_campaigns.id"),
        nullable=True,
        index=True,
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    trigger_event = Column(
        String(100),
        nullable=False,
    )

    channel = Column(
        String(50),
        default="WHATSAPP",
        nullable=False,
    )

    status = Column(
        String(50),
        default="TRIGGERED",
        nullable=False,
    )

    payload = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    customer = relationship("Customer")
    campaign = relationship("Campaign")


class CustomerCoupon(Base):
    """
    Stores which Offer has been assigned to which customer.
    Offer data comes from app.accounts.offer.model.Offer
    """

    __tablename__ = "customer_coupons"

    id = Column(Integer, primary_key=True, index=True)

    customer_id = Column(
        Integer,
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    offer_id = Column(
        Integer,
        ForeignKey("offers.id"),
        nullable=False,
        index=True,
    )

    status = Column(
        String(50),
        default="ISSUED",
        nullable=False,
    )

    issued_reason = Column(
        String(255),
        nullable=True,
    )

    used_at = Column(
        DateTime,
        nullable=True,
    )

    bill_id = Column(
        Integer,
        ForeignKey("bills.id"),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    customer = relationship("Customer")

    offer = relationship("Offer")