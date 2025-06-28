# models/schemas.py
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ListingStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SOLD = "sold"
    ENDED = "ended"

class ItemCondition(str, Enum):
    NEW = "New"
    LIKE_NEW = "Like New"
    VERY_GOOD = "Very Good"
    GOOD = "Good"
    ACCEPTABLE = "Acceptable"
    FOR_PARTS = "For parts or not working"

class ReportType(str, Enum):
    SALES = "sales"
    PERFORMANCE = "performance"
    INVENTORY = "inventory"
    ANALYTICS = "analytics"

class ShippingOption(BaseModel):
    service: str
    cost: float
    estimated_days: int
    free_shipping: bool = False

class ListingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    description: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    quantity: int = Field(..., ge=0)
    category_id: str
    condition: ItemCondition
    images: List[HttpUrl] = Field(default_factory=list, max_items=12)
    item_specifics: Dict[str, str] = Field(default_factory=dict)
    shipping_options: List[ShippingOption] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            HttpUrl: str
        }

class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, min_length=1)
    price: Optional[float] = Field(None, gt=0)
    quantity: Optional[int] = Field(None, ge=0)
    images: Optional[List[HttpUrl]] = Field(None, max_items=12)
    item_specifics: Optional[Dict[str, str]] = None
    shipping_options: Optional[List[ShippingOption]] = None

class ListingResponse(BaseModel):
    id: str
    ebay_listing_id: Optional[str]
    title: str
    description: str
    price: float
    quantity: int
    category_id: str
    condition: str
    status: ListingStatus
    images: List[str]
    views: int
    watchers: int
    sold_quantity: int
    created_at: datetime
    updated_at: datetime
    listed_at: Optional[datetime]
    ends_at: Optional[datetime]

class BulkOperationRequest(BaseModel):
    operation: str = Field(..., pattern="^(update|delete|relist)$")
    listing_ids: List[str] = Field(..., min_items=1)
    data: Optional[Dict[str, Any]] = None

class DateRange(BaseModel):
    start: datetime
    end: datetime

class ReportRequest(BaseModel):
    report_type: ReportType
    date_range: Optional[DateRange] = None
    filters: Optional[Dict[str, Any]] = None

class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    context: Optional[Dict[str, Any]] = None

class CategorySuggestion(BaseModel):
    category_id: str
    category_name: str
    category_path: List[str]
    confidence: float

class OptimizationSuggestion(BaseModel):
    field: str
    current_value: Any
    suggested_value: Any
    reason: str
    impact: str  # low, medium, high

class ListingAnalysis(BaseModel):
    listing_id: str
    performance_score: float
    views: int
    watchers: int
    conversion_rate: float
    price_competitiveness: Dict[str, Any]
    optimization_suggestions: List[OptimizationSuggestion]
    competitor_analysis: Dict[str, Any]

class DashboardAnalytics(BaseModel):
    total_listings: int
    active_listings: int
    total_sales: int
    total_revenue: float
    average_sale_price: float
    top_categories: List[Dict[str, Any]]
    sales_trend: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]

# Authentication schemas
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
