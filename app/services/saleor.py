from typing import List, Optional

# Import the actual generated client
from app.graphql.generated_client import SaleorClient


class SaleorService:
    """
    A service class to handle all interactions with the Saleor GraphQL API.
    """

    def __init__(self, saleor_api_url: str, saleor_api_token: str):
        # The generated client will be used to make actual API calls.
        # It's configured with the URL and an Authorization header for the token.
        self.client = SaleorClient(
            url=saleor_api_url, headers={"Authorization": f"Bearer {saleor_api_token}"}
        )

    async def get_product_from_saleor(self, product_id: str) -> Optional[dict]:
        """Fetches a single product directly from the Saleor API."""
        response = await self.client.get_product(id=product_id)

        if not response or not response.product:
            return None

        product = response.product
        product_data = {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "description": product.description,
            "variants": [],
        }
        if product.variants:
            for variant in product.variants:
                variant_data = {
                    "id": variant.id,
                    "name": variant.name,
                    "sku": variant.sku,
                    "price": (
                        variant.pricing.price.gross.amount
                        if variant.pricing
                        and variant.pricing.price
                        and variant.pricing.price.gross
                        else 0.0
                    ),
                    "currency": (
                        variant.pricing.price.gross.currency
                        if variant.pricing
                        and variant.pricing.price
                        and variant.pricing.price.gross
                        else None
                    ),
                    "stock_quantity": (
                        variant.stocks[0].quantity if variant.stocks else 0
                    ),
                }
                product_data["variants"].append(variant_data)

        return product_data

    async def list_products_by_merchant(
        self, merchant_id: str, first: int = 10, after: Optional[str] = None
    ) -> List[dict]:
        """
        Fetches products filtered by a specific merchant ID from the Saleor API.
        """
        # Call the new generated client method
        response = await self.client.list_products_by_merchant(
            first=first, after=after, merchant_id=merchant_id
        )

        products_data = []
        # Check if the response and products list are valid before processing
        if response and response.products and response.products.edges:
            for edge in response.products.edges:
                node = edge.node

                # Extract the product data to fit our existing Pydantic schema
                product_data = {
                    "id": node.id,
                    "name": node.name,
                    "slug": node.slug,
                    "description": node.description,
                    "variants": [],
                }

                if node.variants:
                    for variant in node.variants:
                        # Safely access nested fields. The new query's structure is a bit
                        # different, so we'll adjust the access path.
                        price_data = (
                            variant.channel_listings[0].price
                            if variant.channel_listings
                            and variant.channel_listings[0].price
                            else None
                        )

                        variant_data = {
                            "id": variant.id,
                            "name": variant.name,
                            "sku": variant.sku,
                            "price": price_data.amount if price_data else 0.0,
                            "currency": price_data.currency if price_data else None,
                            # Note: The provided query for a merchant's products does not include
                            # stock quantity on the variants, so we'll set it to 0.
                            "stock_quantity": 0,
                        }
                        product_data["variants"].append(variant_data)

                products_data.append(product_data)

        return products_data
