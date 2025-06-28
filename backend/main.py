# main.py
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from backend.agents.ebay_agent import EbayListingAgent
from backend.mcp.server import EbayMCPServer
from backend.mcp.handlers import MCPWebhookHandler
from backend.services.ebay_service import EbayService
from backend.services.database_service import DatabaseService
from backend.api.auth import get_current_user
from backend.models.schemas import (
    ListingCreate,
    ListingUpdate,
    ListingResponse,
    BulkOperationRequest,
    ReportRequest,
    AgentQueryRequest
)

# Global instances
ebay_service = None
db_service = None
ebay_agent = None
mcp_server = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global ebay_service, db_service, ebay_agent, mcp_server
    
    # Initialize services
    db_service = DatabaseService()
    await db_service.initialize()
    
    ebay_service = EbayService()
    await ebay_service.initialize()
    
    # Initialize AI agent
    ebay_agent = EbayListingAgent(ebay_service, db_service)
    
    # Initialize MCP server
    mcp_server = EbayMCPServer(ebay_agent)
    
    # Start MCP server in background
    asyncio.create_task(mcp_server.start())
    
    yield
    
    # Cleanup
    await db_service.close()
    await ebay_service.close()

# Create FastAPI app
app = FastAPI(
    title="eBay Listing Manager",
    description="AI-powered eBay listing management system",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the MCP webhook handler
webhook_handler = MCPWebhookHandler(mcp_server)
app.mount("/mcp", webhook_handler.app)

# API Routes
@app.get("/")
async def root():
    return {
        "message": "eBay Listing Manager API",
        "version": "1.0.0",
        "endpoints": {
            "api": "/docs",
            "mcp_webhook": "/mcp/webhook/mcp",
            "mcp_tools": "/mcp/webhook/tools"
        }
    }

@app.post("/api/listings", response_model=ListingResponse)
async def create_listing(
    listing: ListingCreate,
    current_user: Dict = Depends(get_current_user)
):
    """Create a new eBay listing"""
    try:
        # Use the agent to create listing
        result = await ebay_agent.agent.tools[0].function(listing.dict())
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return ListingResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/listings/{listing_id}")
async def update_listing(
    listing_id: str,
    updates: ListingUpdate,
    current_user: Dict = Depends(get_current_user)
):
    """Update an existing listing"""
    try:
        update_data = {
            "listing_id": listing_id,
            "updates": updates.dict(exclude_unset=True)
        }
        
        result = await ebay_agent.agent.tools[1].function(update_data)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/listings")
async def search_listings(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: Dict = Depends(get_current_user)
):
    """Search listings with filters"""
    try:
        criteria = {
            "keyword": keyword,
            "status": status,
            "category": category
        }
        
        result = await ebay_agent.agent.tools[2].function(criteria)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        # Apply pagination
        listings = result["listings"][offset:offset + limit]
        
        return {
            "total": result["count"],
            "limit": limit,
            "offset": offset,
            "listings": listings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/listings/{listing_id}")
async def get_listing(
    listing_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Get a specific listing"""
    try:
        listing = await ebay_service.get_listing(listing_id)
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        return listing
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/listings/{listing_id}")
async def delete_listing(
    listing_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Delete a listing"""
    try:
        result = await ebay_service.delete_listing(listing_id)
        await db_service.delete_listing(listing_id)
        return {"success": True, "message": "Listing deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/listings/{listing_id}/analyze")
async def analyze_listing(
    listing_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """Analyze listing performance"""
    try:
        result = await ebay_agent.agent.tools[3].function(listing_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result["insights"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bulk-operations")
async def bulk_operations(
    request: BulkOperationRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict = Depends(get_current_user)
):
    """Perform bulk operations on listings"""
    try:
        # For long-running operations, use background tasks
        if len(request.listing_ids) > 10:
            background_tasks.add_task(
                perform_bulk_operation,
                request.operation,
                request.listing_ids,
                request.data,
                current_user["id"]
            )
            return {
                "success": True,
                "message": "Bulk operation started in background",
                "task_id": f"bulk_{datetime.now().timestamp()}"
            }
        else:
            # Execute immediately for small batches
            result = await perform_bulk_operation(
                request.operation,
                request.listing_ids,
                request.data,
                current_user["id"]
            )
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reports")
async def generate_report(
    request: ReportRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Generate various reports"""
    try:
        # Use MCP server's report generation
        result = await mcp_server._generate_report({
            "report_type": request.report_type,
            "date_range": request.date_range.dict() if request.date_range else {}
        })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/agent/query")
async def query_agent(
    request: AgentQueryRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Query the AI agent with natural language"""
    try:
        response = await ebay_agent.process_request(request.query)
        
        return {
            "query": request.query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories/suggest")
async def suggest_categories(
    title: str,
    description: Optional[str] = "",
    current_user: Dict = Depends(get_current_user)
):
    """Get category suggestions for a product"""
    try:
        result = await ebay_agent.agent.tools[5].function(title, description)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result["suggestions"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/listings/{listing_id}/optimize")
async def optimize_listing(
    listing_id: str,
    apply: bool = False,
    current_user: Dict = Depends(get_current_user)
):
    """Get optimization suggestions for a listing"""
    try:
        result = await ebay_agent.agent.tools[6].function(listing_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        optimizations = result["optimizations"]
        
        # Apply optimizations if requested
        if apply:
            updates = {
                "title": optimizations["title"],
                "description": optimizations["description"],
                "price": optimizations["pricing"]["suggested_price"]
            }
            
            update_result = await ebay_agent.agent.tools[1].function({
                "listing_id": listing_id,
                "updates": updates
            })
            
            return {
                "optimizations": optimizations,
                "applied": update_result["success"]
            }
        
        return optimizations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/dashboard")
async def get_dashboard_analytics(
    days: int = 30,
    current_user: Dict = Depends(get_current_user)
):
    """Get dashboard analytics"""
    try:
        analytics = await db_service.get_dashboard_analytics(
            user_id=current_user["id"],
            days=days
        )
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    try:
        while True:
            # Send periodic updates
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat()
            })
            await asyncio.sleep(30)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# Helper functions
async def perform_bulk_operation(
    operation: str,
    listing_ids: List[str],
    data: Optional[Dict],
    user_id: str
) -> Dict[str, Any]:
    """Perform bulk operation"""
    if operation == "update" and data:
        result = await ebay_agent.agent.tools[4].function(listing_ids, data)
        return result
    elif operation == "delete":
        results = []
        for listing_id in listing_ids:
            try:
                await ebay_service.delete_listing(listing_id)
                await db_service.delete_listing(listing_id)
                results.append({"listing_id": listing_id, "success": True})
            except Exception as e:
                results.append({
                    "listing_id": listing_id,
                    "success": False,
                    "error": str(e)
                })
        
        success_count = sum(1 for r in results if r["success"])
        return {
            "operation": operation,
            "total": len(listing_ids),
            "successful": success_count,
            "failed": len(listing_ids) - success_count,
            "results": results
        }
    else:
        raise ValueError(f"Unsupported operation: {operation}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )