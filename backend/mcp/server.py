# mcp/server.py
from mcp.server import Server, Request, Response
from mcp.types import (
    Tool, 
    ToolResult, 
    TextContent,
    ImageContent,
    CallToolRequest,
    ListToolsRequest
)
from typing import Dict, Any, List
import asyncio
import json
from datetime import datetime

class EbayMCPServer:
    def __init__(self, ebay_agent):
        self.ebay_agent = ebay_agent
        self.server = Server("ebay-listing-manager")
        
        # Register handlers
        self.server.request_handler(ListToolsRequest)(self.handle_list_tools)
        self.server.request_handler(CallToolRequest)(self.handle_call_tool)
        
        # Define available tools
        self.tools = {
            "create_listing": Tool(
                name="create_listing",
                description="Create a new eBay listing",
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "price": {"type": "number"},
                        "quantity": {"type": "integer"},
                        "category_id": {"type": "string"},
                        "condition": {"type": "string"},
                        "images": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["title", "description", "price", "category_id"]
                }
            ),
            "update_listing": Tool(
                name="update_listing",
                description="Update an existing eBay listing",
                input_schema={
                    "type": "object",
                    "properties": {
                        "listing_id": {"type": "string"},
                        "updates": {"type": "object"}
                    },
                    "required": ["listing_id", "updates"]
                }
            ),
            "search_listings": Tool(
                name="search_listings",
                description="Search for eBay listings",
                input_schema={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string"},
                        "status": {"type": "string"},
                        "category": {"type": "string"}
                    }
                }
            ),
            "analyze_listing": Tool(
                name="analyze_listing",
                description="Analyze listing performance",
                input_schema={
                    "type": "object",
                    "properties": {
                        "listing_id": {"type": "string"}
                    },
                    "required": ["listing_id"]
                }
            ),
            "bulk_operations": Tool(
                name="bulk_operations",
                description="Perform bulk operations on listings",
                input_schema={
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["update", "delete", "relist"]
                        },
                        "listing_ids": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "data": {"type": "object"}
                    },
                    "required": ["operation", "listing_ids"]
                }
            ),
            "generate_report": Tool(
                name="generate_report",
                description="Generate sales and performance reports",
                input_schema={
                    "type": "object",
                    "properties": {
                        "report_type": {
                            "type": "string",
                            "enum": ["sales", "performance", "inventory", "analytics"]
                        },
                        "date_range": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string", "format": "date"},
                                "end": {"type": "string", "format": "date"}
                            }
                        }
                    },
                    "required": ["report_type"]
                }
            ),
            "ai_assistant": Tool(
                name="ai_assistant",
                description="Get AI assistance for eBay listing management",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "context": {"type": "object"}
                    },
                    "required": ["query"]
                }
            )
        }
    
    async def handle_list_tools(self, request: ListToolsRequest) -> List[Tool]:
        """Return available tools"""
        return list(self.tools.values())
    
    async def handle_call_tool(self, request: CallToolRequest) -> ToolResult:
        """Handle tool execution requests"""
        tool_name = request.name
        arguments = request.arguments
        
        try:
            if tool_name == "create_listing":
                result = await self._create_listing(arguments)
            elif tool_name == "update_listing":
                result = await self._update_listing(arguments)
            elif tool_name == "search_listings":
                result = await self._search_listings(arguments)
            elif tool_name == "analyze_listing":
                result = await self._analyze_listing(arguments)
            elif tool_name == "bulk_operations":
                result = await self._bulk_operations(arguments)
            elif tool_name == "generate_report":
                result = await self._generate_report(arguments)
            elif tool_name == "ai_assistant":
                result = await self._ai_assistant(arguments)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            return ToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            )
        
        except Exception as e:
            return ToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "error": str(e),
                        "tool": tool_name,
                        "timestamp": datetime.now().isoformat()
                    })
                )],
                is_error=True
            )
    
    async def _create_listing(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new listing through the agent"""
        # Use the PydanticAI agent's create_listing tool
        listing_details = {
            "title": args["title"],
            "description": args["description"],
            "price": args["price"],
            "quantity": args.get("quantity", 1),
            "category_id": args["category_id"],
            "condition": args.get("condition", "New"),
            "images": args.get("images", [])
        }
        
        # Call the agent's tool directly
        create_tool = next(
            t for t in self.ebay_agent.agent.tools 
            if t.name == "create_listing"
        )
        result = await create_tool.function(listing_details)
        
        return result
    
    async def _update_listing(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing listing"""
        update_data = {
            "listing_id": args["listing_id"],
            "updates": args["updates"]
        }
        
        update_tool = next(
            t for t in self.ebay_agent.agent.tools 
            if t.name == "update_listing"
        )
        result = await update_tool.function(update_data)
        
        return result
    
    async def _search_listings(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for listings"""
        search_criteria = {
            "keyword": args.get("keyword"),
            "status": args.get("status"),
            "category": args.get("category")
        }
        
        search_tool = next(
            t for t in self.ebay_agent.agent.tools 
            if t.name == "search_listings"
        )
        result = await search_tool.function(search_criteria)
        
        return result
    
    async def _analyze_listing(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a listing's performance"""
        analyze_tool = next(
            t for t in self.ebay_agent.agent.tools 
            if t.name == "analyze_listing"
        )
        result = await analyze_tool.function(args["listing_id"])
        
        return result
    
    async def _bulk_operations(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform bulk operations"""
        operation = args["operation"]
        listing_ids = args["listing_ids"]
        data = args.get("data", {})
        
        results = []
        
        if operation == "update":
            bulk_tool = next(
                t for t in self.ebay_agent.agent.tools 
                if t.name == "bulk_update"
            )
            result = await bulk_tool.function(listing_ids, data)
            return result
        
        elif operation == "delete":
            for listing_id in listing_ids:
                try:
                    # Implement delete logic
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
        
        elif operation == "relist":
            for listing_id in listing_ids:
                try:
                    # Implement relist logic
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
        
        return {
            "operation": operation,
            "total": len(listing_ids),
            "results": results
        }
    
    async def _generate_report(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generate various reports"""
        report_type = args["report_type"]
        date_range = args.get("date_range", {})
        
        # Implement report generation based on type
        if report_type == "sales":
            return await self._generate_sales_report(date_range)
        elif report_type == "performance":
            return await self._generate_performance_report(date_range)
        elif report_type == "inventory":
            return await self._generate_inventory_report()
        elif report_type == "analytics":
            return await self._generate_analytics_report(date_range)
        
        return {"error": "Unknown report type"}
    
    async def _ai_assistant(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Process natural language queries through the AI agent"""
        query = args["query"]
        context = args.get("context", {})
        
        # Add context to the query if provided
        if context:
            query = f"Context: {json.dumps(context)}\n\nQuery: {query}"
        
        # Process through the PydanticAI agent
        response = await self.ebay_agent.process_request(query)
        
        return {
            "query": args["query"],
            "response": response,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _generate_sales_report(self, date_range: Dict) -> Dict[str, Any]:
        """Generate sales report"""
        # Implement sales report logic
        return {
            "report_type": "sales",
            "date_range": date_range,
            "total_sales": 0,
            "items_sold": 0,
            "revenue": 0
        }
    
    async def _generate_performance_report(self, date_range: Dict) -> Dict[str, Any]:
        """Generate performance report"""
        # Implement performance report logic
        return {
            "report_type": "performance",
            "date_range": date_range,
            "views": 0,
            "conversion_rate": 0,
            "average_sale_price": 0
        }
    
    async def _generate_inventory_report(self) -> Dict[str, Any]:
        """Generate inventory report"""
        # Implement inventory report logic
        return {
            "report_type": "inventory",
            "total_items": 0,
            "active_listings": 0,
            "out_of_stock": 0
        }
    
    async def _generate_analytics_report(self, date_range: Dict) -> Dict[str, Any]:
        """Generate analytics report"""
        # Implement analytics report logic
        return {
            "report_type": "analytics",
            "date_range": date_range,
            "top_categories": [],
            "best_sellers": [],
            "trends": []
        }
    
    async def start(self, host: str = "localhost", port: int = 3000):
        """Start the MCP server"""
        await self.server.run(host, port)



