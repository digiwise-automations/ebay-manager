# services/ebay_service.py
from ebaysdk.trading import Connection as Trading
from ebaysdk.finding import Connection as Finding
from ebaysdk.shopping import Connection as Shopping
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

class EbayService:
    def __init__(self):
        self.app_id = os.getenv("EBAY_APP_ID")
        self.cert_id = os.getenv("EBAY_CERT_ID")
        self.dev_id = os.getenv("EBAY_DEV_ID")
        self.token = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        
    async def initialize(self):
        """Initialize eBay connections"""
        self.trading_api = Trading(
            appid=self.app_id,
            certid=self.cert_id,
            devid=self.dev_id,
            config_file=None
        )
        
        self.finding_api = Finding(
            appid=self.app_id,
            config_file=None
        )
        
        self.shopping_api = Shopping(
            appid=self.app_id,
            config_file=None
        )
    
    def set_user_token(self, token: str):
        """Set user's eBay auth token"""
        self.token = token
        self.trading_api.config.set('token', token)
    
    async def create_listing(self, listing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new eBay listing"""
        try:
            # Prepare item data for eBay API
            item = {
                'Item': {
                    'Title': listing_data['title'],
                    'Description': listing_data['description'],
                    'PrimaryCategory': {'CategoryID': listing_data['category_id']},
                    'StartPrice': listing_data['price'],
                    'Quantity': listing_data['quantity'],
                    'ConditionID': self._get_condition_id(listing_data['condition']),
                    'Country': 'US',
                    'Currency': 'USD',
                    'DispatchTimeMax': 3,
                    'ListingDuration': 'Days_7',
                    'ListingType': 'FixedPriceItem',
                    'PaymentMethods': ['PayPal'],
                    'PayPalEmailAddress': 'your-paypal@email.com',
                    'PictureDetails': {
                        'PictureURL': listing_data.get('images', [])
                    },
                    'ReturnPolicy': {
                        'ReturnsAcceptedOption': 'ReturnsAccepted',
                        'RefundOption': 'MoneyBack',
                        'ReturnsWithinOption': 'Days_30',
                        'ShippingCostPaidByOption': 'Buyer'
                    },
                    'ShippingDetails': self._prepare_shipping_details(
                        listing_data.get('shipping_options', [])
                    ),
                    'ItemSpecifics': self._prepare_item_specifics(
                        listing_data.get('item_specifics', {})
                    )
                }
            }
            
            # Call eBay API in thread pool
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.trading_api.execute('AddItem', item)
            )
            
            result = response.dict()
            
            if result.get('Ack') == 'Success':
                return {
                    'listing_id': result['ItemID'],
                    'listing_url': f"https://www.ebay.com/itm/{result['ItemID']}",
                    'fees': result.get('Fees', {})
                }
            else:
                raise Exception(f"eBay API error: {result.get('Errors', 'Unknown error')}")
                
        except Exception as e:
            raise Exception(f"Failed to create listing: {str(e)}")
    
    async def update_listing(self, listing_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing listing"""
        try:
            # Prepare revision data
            revision = {
                'Item': {
                    'ItemID': listing_id
                }
            }
            
            # Map updates to eBay fields
            if 'title' in updates:
                revision['Item']['Title'] = updates['title']
            if 'description' in updates:
                revision['Item']['Description'] = updates['description']
            if 'price' in updates:
                revision['Item']['StartPrice'] = updates['price']
            if 'quantity' in updates:
                revision['Item']['Quantity'] = updates['quantity']
            if 'images' in updates:
                revision['Item']['PictureDetails'] = {'PictureURL': updates['images']}
            
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.trading_api.execute('ReviseItem', revision)
            )
            
            result = response.dict()
            
            if result.get('Ack') == 'Success':
                return {
                    'success': True,
                    'fees': result.get('Fees', {})
                }
            else:
                raise Exception(f"eBay API error: {result.get('Errors', 'Unknown error')}")
                
        except Exception as e:
            raise Exception(f"Failed to update listing: {str(e)}")
    
    async def get_listing(self, listing_id: str) -> Dict[str, Any]:
        """Get listing details"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.trading_api.execute('GetItem', {'ItemID': listing_id})
            )
            
            result = response.dict()
            
            if result.get('Ack') == 'Success':
                item = result['Item']
                return self._parse_listing(item)
            else:
                raise Exception(f"eBay API error: {result.get('Errors', 'Unknown error')}")
                
        except Exception as e:
            raise Exception(f"Failed to get listing: {str(e)}")
    
    async def search_listings(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search for listings"""
        try:
            params = {
                'outputSelector': ['ItemID', 'Title', 'CurrentPrice', 'ListingInfo'],
                'paginationInput': {
                    'entriesPerPage': 100,
                    'pageNumber': 1
                }
            }
            
            if criteria.get('keyword'):
                params['keywords'] = criteria['keyword']
            if criteria.get('category'):
                params['categoryId'] = criteria['category']
            
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.finding_api.execute('findItemsAdvanced', params)
            )
            
            result = response.dict()
            items = result.get('searchResult', {}).get('item', [])
            
            return [self._parse_search_result(item) for item in items]
            
        except Exception as e:
            raise Exception(f"Failed to search listings: {str(e)}")
    
    async def delete_listing(self, listing_id: str) -> bool:
        """End a listing"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.trading_api.execute('EndItem', {
                    'ItemID': listing_id,
                    'EndingReason': 'NotAvailable'
                })
            )
            
            result = response.dict()
            return result.get('Ack') == 'Success'
            
        except Exception as e:
            raise Exception(f"Failed to end listing: {str(e)}")
    
    async def get_listing_analytics(self, listing_id: str) -> Dict[str, Any]:
        """Get listing performance analytics"""
        try:
            # Get page views
            traffic_response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.trading_api.execute('GetItem', {
                    'ItemID': listing_id,
                    'IncludeWatchCount': True
                })
            )
            
            item = traffic_response.dict().get('Item', {})
            
            # Get bidding/offer statistics
            stats = {
                'view_count': item.get('HitCount', 0),
                'watch_count': item.get('WatchCount', 0),
                'question_count': item.get('QuestionCount', 0),
                'bid_count': item.get('BidCount', 0),
                'conversion_rate': self._calculate_conversion_rate(item)
            }
            
            return stats
            
        except Exception as e:
            raise Exception(f"Failed to get analytics: {str(e)}")
    
    async def get_category_suggestions(self, title: str, description: str) -> List[Dict[str, Any]]:
        """Get category suggestions for a product"""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: self.trading_api.execute('GetSuggestedCategories', {
                    'Query': title[:50]  # eBay limits query to 50 chars
                })
            )
            
            result = response.dict()
            categories = result.get('SuggestedCategoryArray', {}).get('SuggestedCategory', [])
            
            suggestions = []
            for cat in categories[:5]:  # Top 5 suggestions
                suggestions.append({
                    'category_id': cat.get('Category', {}).get('CategoryID'),
                    'category_name': cat.get('Category', {}).get('CategoryName'),
                    'category_path': self._get_category_path(cat.get('Category', {})),
                    'confidence': float(cat.get('PercentItemsFound', 0))
                })
            
            return suggestions
            
        except Exception as e:
            raise Exception(f"Failed to get category suggestions: {str(e)}")
    
    def _get_condition_id(self, condition: str) -> int:
        """Map condition name to eBay condition ID"""
        condition_map = {
            'New': 1000,
            'Like New': 1500,
            'Very Good': 2000,
            'Good': 3000,
            'Acceptable': 4000,
            'For parts or not working': 7000
        }
        return condition_map.get(condition, 1000)
    
    def _prepare_shipping_details(self, shipping_options: List[Dict]) -> Dict:
        """Prepare shipping details for eBay API"""
        shipping_details = {
            'ShippingType': 'Flat',
            'ShippingServiceOptions': []
        }
        
        for idx, option in enumerate(shipping_options):
            service = {
                'ShippingService': option.get('service', 'USPSPriority'),
                'ShippingServiceCost': option.get('cost', 0),
                'ShippingServicePriority': idx + 1,
                'FreeShipping': option.get('free_shipping', False)
            }
            shipping_details['ShippingServiceOptions'].append(service)
        
        return shipping_details
    
    def _prepare_item_specifics(self, specifics: Dict[str, str]) -> Dict:
        """Prepare item specifics for eBay API"""
        name_value_list = []
        
        for name, value in specifics.items():
            name_value_list.append({
                'Name': name,
                'Value': value
            })
        
        return {'NameValueList': name_value_list} if name_value_list else {}
    
    def _parse_listing(self, item: Dict) -> Dict[str, Any]:
        """Parse eBay item to internal format"""
        return {
            'listing_id': item.get('ItemID'),
            'title': item.get('Title'),
            'description': item.get('Description'),
            'price': float(item.get('StartPrice', {}).get('value', 0)),
            'quantity': int(item.get('Quantity', 0)),
            'category_id': item.get('PrimaryCategory', {}).get('CategoryID'),
            'condition': item.get('ConditionDisplayName'),
            'images': item.get('PictureDetails', {}).get('PictureURL', []),
            'status': item.get('SellingStatus', {}).get('ListingStatus'),
            'views': item.get('HitCount', 0),
            'watchers': item.get('WatchCount', 0),
            'listed_at': item.get('ListingDetails', {}).get('StartTime'),
            'ends_at': item.get('ListingDetails', {}).get('EndTime')
        }
    
    def _parse_search_result(self, item: Dict) -> Dict[str, Any]:
        """Parse search result item"""
        return {
            'listing_id': item.get('itemId'),
            'title': item.get('title'),
            'price': float(item.get('sellingStatus', {}).get('currentPrice', {}).get('value', 0)),
            'listing_url': item.get('viewItemURL'),
            'end_time': item.get('listingInfo', {}).get('endTime')
        }
    
    def _calculate_conversion_rate(self, item: Dict) -> float:
        """Calculate conversion rate"""
        views = item.get('HitCount', 0)
        sold = item.get('QuantitySold', 0)
        
        if views > 0:
            return (sold / views) * 100
        return 0.0
    
    def _get_category_path(self, category: Dict) -> List[str]:
        """Get category breadcrumb path"""
        path = []
        parent_id = category.get('CategoryParentID')
        
        # This is simplified - in production, you'd need to traverse the category tree
        if category.get('CategoryName'):
            path.append(category['CategoryName'])
        
        return path



