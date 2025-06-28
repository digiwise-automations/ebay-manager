# mcp/handlers.py
from fastapi import FastAPI, HTTPException, Request
from typing import Dict, Any
import json

class MCPWebhookHandler:
    def __init__(self, mcp_server: EbayMCPServer):
        self.mcp_server = mcp_server
        self.app = FastAPI()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.post("/webhook/mcp")
        async def handle_webhook(request: Request):
            """Handle incoming MCP webhook requests"""
            try:
                body = await request.json()
                
                # Validate request
                if "tool" not in body or "arguments" not in body:
                    raise HTTPException(
                        status_code=400,
                        detail="Missing required fields: tool, arguments"
                    )
                
                tool_name = body["tool"]
                arguments = body["arguments"]
                
                # Create a CallToolRequest
                tool_request = CallToolRequest(
                    name=tool_name,
                    arguments=arguments
                )
                
                # Execute through MCP server
                result = await self.mcp_server.handle_call_tool(tool_request)
                
                # Parse result
                if result.is_error:
                    raise HTTPException(
                        status_code=500,
                        detail=result.content[0].text
                    )
                
                return {
                    "success": True,
                    "result": json.loads(result.content[0].text)
                }
            
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )
        
        @self.app.get("/webhook/tools")
        async def list_available_tools():
            """List all available MCP tools"""
            tools = await self.mcp_server.handle_list_tools(ListToolsRequest())
            
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "schema": tool.input_schema
                    }
                    for tool in tools
                ]
            }
        
        @self.app.post("/webhook/query")
        async def handle_natural_query(request: Request):
            """Handle natural language queries"""
            try:
                body = await request.json()
                query = body.get("query", "")
                context = body.get("context", {})
                
                if not query:
                    raise HTTPException(
                        status_code=400,
                        detail="Query field is required"
                    )
                
                # Use the AI assistant tool
                result = await self.mcp_server._ai_assistant({
                    "query": query,
                    "context": context
                })
                
                return {
                    "success": True,
                    "result": result
                }
            
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )
