# ebay_agent.py
from pydantic_ai import Agent, Tool
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio

# Define models for eBay listings
class ListingDetails(BaseModel):
    title: str = Field(..., description="Product title")
    description: str = Field(..., description="Product description")
    price: float = Field(..., gt=0, description="Product price")
    quantity: int = Field(..., ge=0, description="Available quantity")
    category_id: str = Field(..., description="eBay category ID")
    condition: str = Field(..., description="Item condition")
    images: List[str] = Field(default_factory=list, description="Image URLs")
    item_specifics: Dict[str, str] = Field(default_factory=dict)
    shipping_options: List[Dict[str, Any]] = Field(default_factory=list)

class ListingUpdate(BaseModel):
    listing_id: str
    updates: Dict[str, Any]

class ListingSearchCriteria(BaseModel):
    keyword: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

# Create the main eBay agent
class EbayListingAgent:
    def __init__(self, ebay_service, db_service):
        self.ebay_service = ebay_service
        self.db_service = db_service
        
        # Initialize the PydanticAI agent
        self.agent = Agent(
            model="gpt-4",  # or your preferred model
            system_prompt="""You are an expert eBay listing manager. 
            Help users create, update, and manage their eBay listings efficiently.
            Provide suggestions for optimizing listings for better visibility and sales.""",
            tools=[
                self.create_listing_tool(),
                self.update_listing_tool(),
                self.search_listings_tool(),
                self.analyze_listing_tool(),
                self.bulk_update_tool(),
                self.get_category_suggestions_tool(),
                self.optimize_listing_tool()
            ]
        )
    
    def create_listing_tool(self) -> Tool:
        @Tool(
            name="create_listing",
            description="Create a new eBay listing",
            parameters_model=ListingDetails
        )
        async def create_listing(details: ListingDetails) -> Dict[str, Any]:
            try:
                # Validate the listing details
                validated = await self._validate_listing(details)
                
                # Create listing via eBay API
                result = await self.ebay_service.create_listing(validated.dict())
                
                # Store in local database
                await self.db_service.store_listing(result)
                
                return {
                    "success": True,
                    "listing_id": result["listing_id"],
                    "url": result["listing_url"],
                    "message": "Listing created successfully"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Failed to create listing"
                }
        
        return create_listing
    
    def update_listing_tool(self) -> Tool:
        @Tool(
            name="update_listing",
            description="Update an existing eBay listing",
            parameters_model=ListingUpdate
        )
        async def update_listing(update: ListingUpdate) -> Dict[str, Any]:
            try:
                # Get current listing
                current = await self.ebay_service.get_listing(update.listing_id)
                
                # Apply updates
                updated = {**current, **update.updates}
                
                # Update via eBay API
                result = await self.ebay_service.update_listing(
                    update.listing_id, 
                    updated
                )
                
                # Update local database
                await self.db_service.update_listing(update.listing_id, updated)
                
                return {
                    "success": True,
                    "listing_id": update.listing_id,
                    "updated_fields": list(update.updates.keys()),
                    "message": "Listing updated successfully"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Failed to update listing"
                }
        
        return update_listing
    
    def search_listings_tool(self) -> Tool:
        @Tool(
            name="search_listings",
            description="Search for listings based on criteria",
            parameters_model=ListingSearchCriteria
        )
        async def search_listings(criteria: ListingSearchCriteria) -> Dict[str, Any]:
            try:
                # Search in both eBay and local database
                ebay_results = await self.ebay_service.search_listings(
                    criteria.dict(exclude_none=True)
                )
                local_results = await self.db_service.search_listings(
                    criteria.dict(exclude_none=True)
                )
                
                # Merge and deduplicate results
                all_listings = self._merge_listings(ebay_results, local_results)
                
                return {
                    "success": True,
                    "count": len(all_listings),
                    "listings": all_listings,
                    "message": f"Found {len(all_listings)} listings"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Search failed"
                }
        
        return search_listings
    
    def analyze_listing_tool(self) -> Tool:
        @Tool(
            name="analyze_listing",
            description="Analyze listing performance and provide insights"
        )
        async def analyze_listing(listing_id: str) -> Dict[str, Any]:
            try:
                # Get listing data
                listing = await self.ebay_service.get_listing(listing_id)
                analytics = await self.ebay_service.get_listing_analytics(listing_id)
                
                # Perform analysis
                insights = {
                    "views": analytics.get("view_count", 0),
                    "watchers": analytics.get("watch_count", 0),
                    "conversion_rate": analytics.get("conversion_rate", 0),
                    "price_competitiveness": await self._analyze_pricing(listing),
                    "optimization_suggestions": await self._get_suggestions(listing),
                    "competitor_analysis": await self._analyze_competitors(listing)
                }
                
                return {
                    "success": True,
                    "listing_id": listing_id,
                    "insights": insights,
                    "message": "Analysis complete"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Analysis failed"
                }
        
        return analyze_listing
    
    def bulk_update_tool(self) -> Tool:
        @Tool(
            name="bulk_update",
            description="Update multiple listings at once"
        )
        async def bulk_update(
            listing_ids: List[str], 
            updates: Dict[str, Any]
        ) -> Dict[str, Any]:
            results = []
            
            for listing_id in listing_ids:
                try:
                    result = await self.ebay_service.update_listing(
                        listing_id, 
                        updates
                    )
                    results.append({
                        "listing_id": listing_id,
                        "success": True
                    })
                except Exception as e:
                    results.append({
                        "listing_id": listing_id,
                        "success": False,
                        "error": str(e)
                    })
            
            success_count = sum(1 for r in results if r["success"])
            
            return {
                "success": success_count > 0,
                "total": len(listing_ids),
                "successful": success_count,
                "failed": len(listing_ids) - success_count,
                "results": results,
                "message": f"Updated {success_count} of {len(listing_ids)} listings"
            }
        
        return bulk_update
    
    def get_category_suggestions_tool(self) -> Tool:
        @Tool(
            name="suggest_categories",
            description="Get category suggestions for a product"
        )
        async def suggest_categories(
            title: str, 
            description: str
        ) -> Dict[str, Any]:
            try:
                suggestions = await self.ebay_service.get_category_suggestions(
                    title, 
                    description
                )
                
                return {
                    "success": True,
                    "suggestions": suggestions,
                    "message": f"Found {len(suggestions)} category suggestions"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Failed to get suggestions"
                }
        
        return suggest_categories
    
    def optimize_listing_tool(self) -> Tool:
        @Tool(
            name="optimize_listing",
            description="Optimize listing for better visibility and sales"
        )
        async def optimize_listing(listing_id: str) -> Dict[str, Any]:
            try:
                listing = await self.ebay_service.get_listing(listing_id)
                
                optimizations = {
                    "title": await self._optimize_title(listing["title"]),
                    "description": await self._optimize_description(listing["description"]),
                    "keywords": await self._extract_keywords(listing),
                    "pricing": await self._optimize_pricing(listing),
                    "images": await self._suggest_image_improvements(listing["images"])
                }
                
                # Apply optimizations if confirmed
                return {
                    "success": True,
                    "listing_id": listing_id,
                    "optimizations": optimizations,
                    "message": "Optimization suggestions generated"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Optimization failed"
                }
        
        return optimize_listing
    
    async def _validate_listing(self, details: ListingDetails) -> ListingDetails:
        """Validate and enhance listing details"""
        # Add validation logic here
        return details
    
    async def _analyze_pricing(self, listing: Dict) -> Dict[str, Any]:
        """Analyze pricing competitiveness"""
        # Implement pricing analysis
        return {"competitive": True, "suggested_price": listing["price"]}
    
    async def _get_suggestions(self, listing: Dict) -> List[str]:
        """Get optimization suggestions"""
        suggestions = []
        
        if len(listing.get("title", "")) < 50:
            suggestions.append("Consider adding more keywords to your title")
        
        if len(listing.get("images", [])) < 3:
            suggestions.append("Add more images to increase buyer confidence")
        
        return suggestions
    
    async def _analyze_competitors(self, listing: Dict) -> Dict[str, Any]:
        """Analyze competitor listings"""
        # Implement competitor analysis
        return {"average_price": 0, "total_competitors": 0}
    
    def _merge_listings(self, ebay: List[Dict], local: List[Dict]) -> List[Dict]:
        """Merge and deduplicate listings from different sources"""
        # Implement merging logic
        return ebay + local
    
    async def _optimize_title(self, title: str) -> str:
        """Optimize listing title"""
        # Implement title optimization
        return title
    
    async def _optimize_description(self, description: str) -> str:
        """Optimize listing description"""
        # Implement description optimization
        return description
    
    async def _extract_keywords(self, listing: Dict) -> List[str]:
        """Extract relevant keywords"""
        # Implement keyword extraction
        return []
    
    async def _optimize_pricing(self, listing: Dict) -> Dict[str, Any]:
        """Optimize pricing strategy"""
        # Implement pricing optimization
        return {"suggested_price": listing["price"]}
    
    async def _suggest_image_improvements(self, images: List[str]) -> List[str]:
        """Suggest image improvements"""
        # Implement image analysis
        return ["Add more product angles", "Improve lighting"]

    async def process_request(self, user_input: str) -> str:
        """Process a user request through the agent"""
        response = await self.agent.run(user_input)
        return response