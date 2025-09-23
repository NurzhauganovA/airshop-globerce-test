# mappers/order_mapper.py
from app.schemas.order_schemas import SaleorOrderSchema, CustomerBaseSchema
from app.graphql.generated_client.get_order_by_id import GetOrderByIDOrder

def map_get_order_by_id(order: GetOrderByIDOrder) -> SaleorOrderSchema:
    """Маппинг GraphQL-объекта GetOrderByIDOrder -> Pydantic SaleorOrderSchema"""

    return SaleorOrderSchema(
        id=order.id,
        order=OrderBaseSchema(
            number=order.number,
            status=order.status,
            total_amount=order.total.gross.amount if order.total else None,
            created=order.created,
        ),
        customer=CustomerBaseSchema(
            id=order.user.id if order.user else None,
            email=order.user.email if order.user else None,
            first_name=order.user.first_name if order.user else None,
            last_name=order.user.last_name if order.user else None,
        ) if order.user else None,
    )
