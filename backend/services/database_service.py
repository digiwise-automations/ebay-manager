# services/database_service.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, and_, or_, func
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os

from backend.models.database import Base, User, Listing, ListingTemplate, ListingAnalytics, AgentLog

class DatabaseService:
    def __init__(self):
        self.database_url = os.getenv(
            "DATABASE_URL", 
            "postgresql+asyncpg://user:password@localhost/ebay_manager"
        )
        self.engine = None
        self.async_session = None
    
    async def initialize(self):
        """Initialize database connection"""
        self.engine = create_async_engine(
            self.database_url,
            echo=True  # Set to False in production
        )
        
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
    
    async def create_user(self, email: str, ebay_user_id: Optional[str] = None) -> User:
        """Create a new user"""
        async with self.async_session() as session:
            user = User(
                email=email,
                ebay_user_id=ebay_user_id
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    
    async def store_listing(self, listing_data: Dict[str, Any]) -> Listing:
        """Store listing in database"""
        async with self.async_session() as session:
            listing = Listing(
                ebay_listing_id=listing_data.get('listing_id'),
                user_id=listing_data.get('user_id'),
                title=listing_data['title'],
                description=listing_data['description'],
                price=listing_data['price'],
                quantity=listing_data['quantity'],
                category_id=listing_data['category_id'],
                condition=listing_data['condition'],
                status='active',
                images=listing_data.get('images', []),
                item_specifics=listing_data.get('item_specifics', {}),
                shipping_options=listing_data.get('shipping_options', []),
                listed_at=datetime.utcnow()
            )
            session.add(listing)
            await session.commit()
            await session.refresh(listing)
            return listing
    
    async def update_listing(self, listing_id: str, updates: Dict[str, Any]) -> Listing:
        """Update listing in database"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Listing).where(
                    or_(
                        Listing.id == listing_id,
                        Listing.ebay_listing_id == listing_id
                    )
                )
            )
            listing = result.scalar_one_or_none()
            
            if listing:
                for key, value in updates.items():
                    if hasattr(listing, key):
                        setattr(listing, key, value)
                
                listing.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(listing)
            
            return listing
    
    async def delete_listing(self, listing_id: str) -> bool:
        """Delete listing from database"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Listing).where(
                    or_(
                        Listing.id == listing_id,
                        Listing.ebay_listing_id == listing_id
                    )
                )
            )
            listing = result.scalar_one_or_none()
            
            if listing:
                await session.delete(listing)
                await session.commit()
                return True
            
            return False
    
    async def search_listings(self, criteria: Dict[str, Any]) -> List[Listing]:
        """Search listings in database"""
        async with self.async_session() as session:
            query = select(Listing)
            
            if criteria.get('keyword'):
                keyword = f"%{criteria['keyword']}%"
                query = query.where(
                    or_(
                        Listing.title.ilike(keyword),
                        Listing.description.ilike(keyword)
                    )
                )
            
            if criteria.get('status'):
                query = query.where(Listing.status == criteria['status'])
            
            if criteria.get('category'):
                query = query.where(Listing.category_id == criteria['category'])
            
            if criteria.get('user_id'):
                query = query.where(Listing.user_id == criteria['user_id'])
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def save_template(self, user_id: str, name: str, template_data: Dict) -> ListingTemplate:
        """Save listing template"""
        async with self.async_session() as session:
            template = ListingTemplate(
                user_id=user_id,
                name=name,
                template_data=template_data
            )
            session.add(template)
            await session.commit()
            await session.refresh(template)
            return template
    
    async def get_templates(self, user_id: str) -> List[ListingTemplate]:
        """Get user's templates"""
        async with self.async_session() as session:
            result = await session.execute(
                select(ListingTemplate).where(ListingTemplate.user_id == user_id)
            )
            return result.scalars().all()
    
    async def log_agent_action(
        self, 
        user_id: str, 
        action: str, 
        input_data: Dict, 
        output_data: Dict, 
        success: bool,
        error_message: Optional[str] = None
    ):
        """Log agent action"""
        async with self.async_session() as session:
            log = AgentLog(
                user_id=user_id,
                action=action,
                input_data=input_data,
                output_data=output_data,
                success=success,
                error_message=error_message
            )
            session.add(log)
            await session.commit()
    
    async def save_analytics(self, listing_id: str, analytics_data: Dict):
        """Save listing analytics"""
        async with self.async_session() as session:
            analytics = ListingAnalytics(
                listing_id=listing_id,
                date=datetime.utcnow().date(),
                views=analytics_data.get('views', 0),
                clicks=analytics_data.get('clicks', 0),
                watchers=analytics_data.get('watchers', 0),
                questions=analytics_data.get('questions', 0),
                sales=analytics_data.get('sales', 0),
                revenue=analytics_data.get('revenue', 0.0)
            )
            session.add(analytics)
            await session.commit()
    
    async def get_dashboard_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get dashboard analytics"""
        async with self.async_session() as session:
            # Date range
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get listings
            listings_result = await session.execute(
                select(Listing).where(Listing.user_id == user_id)
            )
            listings = listings_result.scalars().all()
            
            # Calculate metrics
            total_listings = len(listings)
            active_listings = len([l for l in listings if l.status == 'active'])
            
            # Get sales data
            total_sales = sum(l.sold_quantity for l in listings)
            total_revenue = sum(l.sold_quantity * l.price for l in listings)
            
            # Get analytics data
            analytics_result = await session.execute(
                select(ListingAnalytics).where(
                    and_(
                        ListingAnalytics.listing_id.in_([l.id for l in listings]),
                        ListingAnalytics.date >= start_date
                    )
                )
            )
            analytics = analytics_result.scalars().all()
            
            # Aggregate analytics
            total_views = sum(a.views for a in analytics)
            total_watchers = sum(a.watchers for a in analytics)
            
            return {
                'total_listings': total_listings,
                'active_listings': active_listings,
                'total_sales': total_sales,
                'total_revenue': total_revenue,
                'average_sale_price': total_revenue / total_sales if total_sales > 0 else 0,
                'total_views': total_views,
                'total_watchers': total_watchers,
                'conversion_rate': (total_sales / total_views * 100) if total_views > 0 else 0
            }
