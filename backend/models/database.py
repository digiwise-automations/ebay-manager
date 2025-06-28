# models/database.py
from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    ebay_user_id = Column(String, unique=True)
    ebay_token = Column(Text)  # Encrypted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    listings = relationship("Listing", back_populates="user")
    templates = relationship("ListingTemplate", back_populates="user")

class Listing(Base):
    __tablename__ = "listings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ebay_listing_id = Column(String, unique=True)
    user_id = Column(String, ForeignKey("users.id"))
    
    title = Column(String, nullable=False)
    description = Column(Text)
    price = Column(Float)
    quantity = Column(Integer)
    category_id = Column(String)
    condition = Column(String)
    status = Column(String)  # active, sold, ended, draft
    
    images = Column(JSON)  # List of image URLs
    item_specifics = Column(JSON)
    shipping_options = Column(JSON)
    
    views = Column(Integer, default=0)
    watchers = Column(Integer, default=0)
    sold_quantity = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    listed_at = Column(DateTime)
    ends_at = Column(DateTime)
    
    user = relationship("User", back_populates="listings")
    analytics = relationship("ListingAnalytics", back_populates="listing")

class ListingTemplate(Base):
    __tablename__ = "listing_templates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    
    template_data = Column(JSON)  # All listing fields
    is_default = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="templates")

class ListingAnalytics(Base):
    __tablename__ = "listing_analytics"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String, ForeignKey("listings.id"))
    date = Column(DateTime, nullable=False)
    
    views = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    watchers = Column(Integer, default=0)
    questions = Column(Integer, default=0)
    sales = Column(Integer, default=0)
    revenue = Column(Float, default=0.0)
    
    listing = relationship("Listing", back_populates="analytics")

class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    
    action = Column(String)  # Tool name
    input_data = Column(JSON)
    output_data = Column(JSON)
    success = Column(Boolean)
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)


