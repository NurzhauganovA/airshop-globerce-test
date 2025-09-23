from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import (
    Depends,
    HTTPException,
    status,
    Query,
    UploadFile,
    File,
    APIRouter,
)
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from app.controllers import merchant_controller
from app.services.freedom_terminal import freedom_terminal
from app.services.mfo.freedom_mfo import FreedomMfoService
from app.services.saleor import SaleorService

router = APIRouter()

# generate method for create quick airlink
# method should get QuickAirlinkRequest schema and return created airlink
# method should use airlink controller methods
from app.core.database import get_db
from app.controllers.airlink_controller import AirlinkController
from app.controllers.internal import city_controller, address_controller
from app.controllers.merchant_controller import (
    add_category_to_merchant,
    add_shipping_zone_to_merchant,
    list_shipping_zones_for_merchant,
    get_merchant_shipping_zone_by_name,
    get_merchant_shipping_zone_by_id,
    get_merchant_warehouse_by_id,
    create_db_merchant_warehouse,
    list_merchant_warehouses, list_orders_for_merchant_with_transactions, enrich_orders_with_customers,
)
from app.controllers.merchant_site_controller import merchant_site_controller
from app.core import security
from app.core.config import settings
from app.core.s3_client import s3_client
from app.graphql.generated_client import (
    WarehouseCreateInput,
    AddressInput,
    ChannelUpdateInput,
    ShippingMethodChannelListingAddInput,
    WarehouseUpdateInput,
    StockInput, OrderFilterInput,
)
from app.graphql.generated_client.client import CategoryWhereInput, WarehouseFilterInput
from app.models.internal_model import User, Airlink
from app.pagination.cursor_pagination import (
    CursorPageWithOutTotal,
    CursorParamsWithOutTotal,
)
from app.schemas.airlink_schemas import (
    QuickAirlinkResponse,
    QuickAirlinkRequest,
    AirlinkCreateRequest,
    QuickAirlinkStatus,
    AirlinkResponseSchema,
    AirlinkImages,
    AirlinkPatchRequestRequest,
    AirlinkUpdateRequest,
)
from app.schemas.category_schemas import CategoryListSchema
from app.schemas.employee_schemas import (
    EmployeeListSchema,
    BaseEmployeeSchema,
    EmployeeSimpleAddSchema,
)
from app.schemas.merchant_site_shemas import (
    MerchantSiteCreateSchema,
    MerchantSiteUpdateSchema,
    MerchantSiteCarouselItemSchema,
    MerchantSiteSchema,
)
from app.schemas.order_schemas import (
    SaleorOrdersListSchema,
    MerchantPaymentMethodSchema,
    MerchantPaymentMethodPaginatedResponse, SaleorOrderSchema,
)
from app.schemas.product_schemas import (
    CreateProductRequestSchema,
    CreateProductResponseSchema,
)
from app.schemas.warehouse_schemas import (
    MerchantWarehouseSchema,
    ShippingZoneSchema,
    CreateShippingZoneRequest,
    AddShippingMethodToShippingZoneRequest,
    FullShippingZoneSchema,
    ShippingMethodSchema,
    ShippingMethodPriceSchema,
    PatchMerchantWarehouseSchema,
    CreateProductStockSchema,
)
from app.schemas.warehouse_schemas import (
    PaginatedMerchantWarehousesResponse,
    WarehouseSchema,
    ShippingZonesModelListSchema,
    PatchShippingZoneRequest,
    CreateMerchantWarehouseSchema,
)
from app.controllers.internal import user_controller
from app.worker import process_quick_airlink
from app.schemas.address_schema import AddressCustomerInputSchema

airlink_controller = AirlinkController(Airlink)  # Correctly instantiate with model
saleor_service = SaleorService(settings.SALEOR_GRAPHQL_URL, settings.SALEOR_API_TOKEN)
mfoService = FreedomMfoService(settings.FREEDOM_MFO_HOST)

router = APIRouter()


@router.post(
    "/airlinks/quick",
    response_model=QuickAirlinkResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Merchant"],
)
async def create_quick_airlink(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Quickly creates an Airlink with a single product and image.
    The `airlink_in` data can be optionally provided as a JSON string in a form field.
    Automatically assigns to the current merchant user.
    """
    airlink_in = QuickAirlinkRequest()

    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can create Airlinks.",
        )

    if not current_user.merchants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any merchant.",
        )
    merchant_id = current_user.merchants[0].id

    # Upload image to S3
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only images are allowed.",
        )

    try:
        file_url = s3_client.upload_file(file, folder="airlink-images")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )
    try:
        # Create an quick airlink
        fast_airlink = airlink_controller.create_airlink(
            db,
            airlink_in=AirlinkCreateRequest(
                name=airlink_in.name,
                description=airlink_in.description,
                date_start=datetime.now(),
                status="PENDING",
                planned_price=float(0),
                date_end=datetime.now() + timedelta(days=14),
                merchant_id=merchant_id,
                images=[
                    {
                        "url": file_url,
                        "is_main": True,
                    }
                ],
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Airlink: {str(e)}",
        )

    # call celery job to process airlink status
    process_quick_airlink.delay(fast_airlink.id)
    # Limit creation of quick airlinks for merchant
    return {"airlink_id": fast_airlink.id, "status": "PENDING"}


# Create quick airlink status to retrieve processin status of airlink
@router.get(
    "/airlinks/quick/{airlink_id}/status",
    response_model=QuickAirlinkStatus,
    tags=["Merchant"],
)
async def get_quick_airlink_status(
    airlink_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Retrieves the status of a quick Airlink.
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view Airlink status.",
        )

    airlink = airlink_controller.get_airlink_by_id(db, airlink_id)

    if not airlink:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Airlink not found."
        )

    # Ensure the merchant owns the airlink
    if not current_user.merchants or airlink.merchant_id not in [
        m.id for m in current_user.merchants
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this Airlink.",
        )

    # Convert Airlink model to AirlinkResponseSchema for preview
    airlink_response = AirlinkResponseSchema(
        id=airlink.id,
        moderation_status=airlink.moderation_status,
        name=airlink.name,
        description=airlink.description,
        date_start=airlink.date_start,
        date_end=airlink.date_end,
        merchant_id=airlink.merchant_id,
        created_at=airlink.created_at,
        updated_at=airlink.updated_at,
        total_price=(
            airlink.total_price if airlink.total_price is not None else Decimal(0)
        ),
        images=[AirlinkImages(url=img.url, is_main=False) for img in airlink.images],
        public_url=airlink.public_url,
        published=airlink.published,
    )

    return QuickAirlinkStatus(
        airlink_id=airlink.id,
        status=airlink.moderation_status,
        preview=airlink_response,
    )


# Publish airlink
@router.post(
    "/airlinks/{airlink_id}/publish",
    response_model=AirlinkResponseSchema,
    tags=["Merchant"],
)
async def publish_airlink(
    airlink_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Publishes an Airlink, making it visible to customers.
    Only merchants who own the Airlink can publish it.
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can publish Airlinks.",
        )

    airlink = airlink_controller.get_airlink_by_id(db, airlink_id)

    if not airlink:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Airlink not found."
        )

    # Ensure the merchant owns the airlink
    if not current_user.merchants or airlink.merchant_id not in [
        m.id for m in current_user.merchants
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to publish this Airlink.",
        )

    if airlink.moderation_status != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Airlink must be APPROVED before it can be published.",
        )

    if airlink.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Airlink is already published.",
        )

    if airlink.planned_price < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planned price is low",
        )

    print(f"Airlink planned price: {airlink.planned_price}")

    airlink_controller.publish_airlink(db, airlink)

    return AirlinkResponseSchema(
        id=airlink.id,
        moderation_status=airlink.moderation_status,
        name=airlink.name,
        description=airlink.description,
        date_start=airlink.date_start,
        date_end=airlink.date_end,
        merchant_id=airlink.merchant_id,
        created_at=airlink.created_at,
        updated_at=airlink.updated_at,
        total_price=(
            airlink.total_price if airlink.total_price is not None else Decimal(0)
        ),
        images=[AirlinkImages(url=img.url, is_main=False) for img in airlink.images],
        public_url=airlink.public_url,
        published=airlink.published,
    )

@router.patch(
    "/airlinks/{airlink_id}/prolong",
    response_model=AirlinkResponseSchema,
    tags=["Merchant"],
)
async def prolong_airlink(
    airlink_id: str,
    db: Session = Depends(get_db),
    days_to_increase: Optional[int] = Query(
        settings.AIRLINK_PROLONG_DAYS,
        description="Override default 14 days range",
    ),
    current_user: User = Depends(security.get_current_user),
):
    """
    Publishes an Airlink, making it visible to customers.
    Only merchants who own the Airlink can publish it.
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can publish Airlinks.",
        )

    airlink = airlink_controller.get_airlink_by_id(db, airlink_id)

    if not airlink:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Airlink not found."
        )

    # Ensure the merchant owns the airlink
    if not current_user.merchants or airlink.merchant_id not in [
        m.id for m in current_user.merchants
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to publish this Airlink.",
        )

    airlink.date_end += timedelta(days=days_to_increase)
    db.commit()
    db.refresh(airlink)

    return AirlinkResponseSchema(
        id=airlink.id,
        moderation_status=airlink.moderation_status,
        name=airlink.name,
        description=airlink.description,
        date_start=airlink.date_start,
        date_end=airlink.date_end,
        merchant_id=airlink.merchant_id,
        created_at=airlink.created_at,
        updated_at=airlink.updated_at,
        total_price=(
            airlink.total_price if airlink.total_price is not None else Decimal(0)
        ),
        images=[AirlinkImages(url=img.url, is_main=False) for img in airlink.images],
        public_url=airlink.public_url,
        published=airlink.published,
    )


@router.post(
    "/airlinks/{airlink_id}/unpublish",
    response_model=AirlinkResponseSchema,
    tags=["Merchant"],
)
async def unpublish_airlink(
    airlink_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Unpublishes an Airlink, making it no longer visible to customers.
    Only merchants who own the Airlink can unpublish it.
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can unpublish Airlinks.",
        )

    airlink = airlink_controller.get_airlink_by_id(db, airlink_id)

    if not airlink:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Airlink not found."
        )

    # Ensure the merchant owns the airlink
    if not current_user.merchants or airlink.merchant_id not in [
        m.id for m in current_user.merchants
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to unpublish this Airlink.",
        )

    if not airlink.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Airlink is already unpublished.",
        )

    airlink_controller.unpublish_airlink(db, airlink)

    return AirlinkResponseSchema(
        id=airlink.id,
        moderation_status=airlink.moderation_status,
        name=airlink.name,
        description=airlink.description,
        date_start=airlink.date_start,
        date_end=airlink.date_end,
        merchant_id=airlink.merchant_id,
        created_at=airlink.created_at,
        updated_at=airlink.updated_at,
        total_price=(
            airlink.total_price if airlink.total_price is not None else Decimal(0)
        ),
        images=[AirlinkImages(url=img.url, is_main=False) for img in airlink.images],
        public_url=airlink.public_url,
        published=airlink.published,
    )


# Get list of airlinks with sorting, ordering limits and etc
@router.get(
    "/airlinks",
    response_model=CursorPageWithOutTotal[AirlinkResponseSchema],
    tags=["Merchant"],
)
async def get_merchant_airlinks(
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
    params: CursorParamsWithOutTotal = Depends(),
    moderation_status: Optional[str] = Query(
        None,
        description="Filter by moderation status (e.g., PENDING, APPROVED, REJECTED)",
    ),
    published: Optional[bool] = Query(
        None, description="Filter by published status (true or false)"
    ),
):
    """
    Retrieves a list of Airlinks for the current merchant with filtering, sorting, and pagination.
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view Airlinks.",
        )

    if not current_user.merchants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any merchant.",
        )
    merchant_id = current_user.merchants[0].id

    query = airlink_controller.get_cursor_query(db).filter(
        Airlink.merchant_id == merchant_id
    )

    if moderation_status:
        query = query.filter(Airlink.moderation_status == moderation_status.upper())

    if published is not None:
        query = query.filter(Airlink.published == published)

    return paginate(db, query, params)


@router.get(
    "/airlinks/{airlink_id}",
    response_model=AirlinkResponseSchema,
    tags=["Merchant"],
)
async def get_merchant_airlink(
    airlink_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    """
    Retrieves a list of Airlinks for the current merchant with filtering, sorting, and pagination.
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view Airlinks.",
        )

    if not current_user.merchants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any merchant.",
        )
    merchant_id = current_user.merchants[0].id

    airlink = airlink_controller.get_airlink_by_id(db, airlink_id)

    if not airlink:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Airlink not found."
        )

    if airlink.merchant_id != merchant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Airlink not found."
        )

    return AirlinkResponseSchema(
        id=airlink.id,
        moderation_status=airlink.moderation_status,
        name=airlink.name,
        description=airlink.description,
        date_start=airlink.date_start,
        date_end=airlink.date_end,
        merchant_id=airlink.merchant_id,
        created_at=airlink.created_at,
        updated_at=airlink.updated_at,
        total_price=(
            airlink.total_price if airlink.total_price is not None else Decimal(0)
        ),
        planned_price=airlink.planned_price,
        images=[AirlinkImages(url=img.url, is_main=False) for img in airlink.images],
        public_url=airlink.public_url,
        published=airlink.published,
    )


@router.post("/airlinks")
async def create_airlink():
    pass


@router.patch("/airlinks/{airlink_id}", response_model=AirlinkResponseSchema)
async def update_airlink(
    airlink_id: str,
    request: AirlinkPatchRequestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    airlink = airlink_controller.get_airlink_by_id(db=db, airlink_id=airlink_id)

    if not airlink:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airlink not found.",
        )

    if airlink.merchant_id != merchant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this airlink.",
        )

    variant = airlink.checkout_items[0]
    variant_id = variant.saleor_variant_id

    if request.price:
        set_price_request = await saleor_service.client.variant_set_price(
            variant_id=variant_id,
            channel_id=settings.LINK_SALEOR_CHANNEL_ID,
            price=request.price,
        )

        if set_price_request.product_variant_channel_listing_update.errors:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update variant price: {set_price_request.product_variant_channel_listing_update.errors}",
            )

    updated_airlink = airlink_controller.update_airlink(
        db=db,
        db_airlink=airlink,
        airlink_update=AirlinkUpdateRequest(
            name=request.name if request.name else airlink.name,
            description=(
                request.description if request.description else airlink.description
            ),
            planned_price=request.price if request.price else airlink.planned_price,
            date_end=request.date_end if request.date_end else airlink.date_end,
            date_start=request.date_start if request.date_start else airlink.date_start,
        ),
    )

    return AirlinkResponseSchema(
        id=updated_airlink.id,
        moderation_status=updated_airlink.moderation_status,
        name=updated_airlink.name,
        description=updated_airlink.description,
        date_start=updated_airlink.date_start,
        date_end=updated_airlink.date_end,
        merchant_id=updated_airlink.merchant_id,
        created_at=updated_airlink.created_at,
        updated_at=updated_airlink.updated_at,
        total_price=(
            updated_airlink.total_price
            if updated_airlink.total_price is not None
            else Decimal(0)
        ),
        planned_price=updated_airlink.planned_price,
        images=[
            AirlinkImages(url=img.url, is_main=False) for img in updated_airlink.images
        ],
        public_url=updated_airlink.public_url,
        published=updated_airlink.published,
    )


@router.get("/products")
async def list_products_for_merchant(
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    products_list_response = await saleor_service.client.list_products_by_merchant(
        merchant_id=merchant.id, first=30
    )

    return products_list_response.products.edges


@router.post("/products", response_model=CreateProductResponseSchema)
async def create_product(
    request: CreateProductRequestSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can create products",
        )

    merchant = current_user.merchants[0]

    merchant_category = add_category_to_merchant(
        db=db, merchant=merchant, category_id=request.category_id
    )

    create_product_response = await saleor_service.client.create_product_for_merchant(
        product_type=settings.MERCHANT_PRODUCT_TYPE,
        category=merchant_category.saleor_category_id,
        merchant_id=merchant_category.merchant_id,
        name=request.name,
    )
    if (
        not create_product_response.product_create
        or not create_product_response.product_create.product
        or create_product_response.product_create.errors
    ):
        errors = (
            create_product_response.product_create.errors
            if create_product_response.product_create
            else "Unknown error"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create product: {errors}",
        )

    product_id = create_product_response.product_create.product.id
    variant_response = await saleor_service.client.create_variant_for_product(
        product_id=product_id,
        sku=request.sku,
        name=request.name,
    )
    if (
        not variant_response.product_variant_create
        or not variant_response.product_variant_create.product_variant
        or variant_response.product_variant_create.errors
    ):
        errors = (
            variant_response.product_variant_create.errors
            if variant_response.product_variant_create
            else "Unknown error"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create variant: {errors}",
        )

    variant_id = variant_response.product_variant_create.product_variant.id
    await saleor_service.client.add_product_to_channel(
        product_id=product_id, chanel_id=settings.LINK_SALEOR_CHANNEL_ID
    )

    await saleor_service.client.variant_set_price(
        variant_id=variant_id,
        channel_id=settings.LINK_SALEOR_CHANNEL_ID,
        price=request.price,
    )

    return CreateProductResponseSchema(
        product_id=product_id,
        product_name=create_product_response.product_create.product.name,
        product_slug=create_product_response.product_create.product.slug,
        variant_id=variant_id,
        variant_name=variant_response.product_variant_create.product_variant.name,
        merchant_id=merchant_category.merchant_id,
    )


@router.patch("/products/{product_id}")
async def update_product():
    pass


@router.get("/warehouses", response_model=PaginatedMerchantWarehousesResponse)
async def list_warehouses_for_merchant(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
    first: Optional[int] = Query(
        25, description="Returns the first n elements from the list."
    ),
    last: Optional[int] = Query(
        None, description="Returns the last n elements from the list."
    ),
    after: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come after the specified cursor.",
    ),
    before: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come before the specified cursor.",
    ),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    warehouses_list = list_merchant_warehouses(db=db, merchant_id=merchant.id)
    print([wh.__dict__ for wh in warehouses_list])
    filter_input = WarehouseFilterInput(
        ids=[wh.saleor_warehouse_id for wh in warehouses_list]
    )

    saleor_warehouses_response = await saleor_service.client.get_warehouses(
        filter=filter_input, first=first, last=last, after=after, before=before
    )

    saleor_warehouses = saleor_warehouses_response.warehouses.edges

    db_wh_map = {wh.saleor_warehouse_id: wh for wh in warehouses_list}

    combined_warehouses = []
    for edge in saleor_warehouses:
        saleor_wh_node = edge.node
        db_wh = db_wh_map.get(saleor_wh_node.id)
        if db_wh:
            combined_warehouses.append(
                MerchantWarehouseSchema(
                    id=db_wh.id,
                    saleor_warehouse_id=db_wh.saleor_warehouse_id,
                    merchant_id=db_wh.merchant_id,
                    warehouse=WarehouseSchema(
                        id=saleor_wh_node.id,
                        name=saleor_wh_node.name,
                        slug=saleor_wh_node.slug,
                    ),
                    address=AddressCustomerInputSchema.load_address_by_id(db=db, address_id=db_wh.address_id),
                )
            )

    page_info = saleor_warehouses_response.warehouses.page_info

    return PaginatedMerchantWarehousesResponse(
        items=combined_warehouses,
        total_count=saleor_warehouses_response.warehouses.total_count or 0,
        has_next_page=page_info.has_next_page,
        has_previous_page=page_info.has_previous_page,
        start=page_info.start_cursor,
        end=page_info.end_cursor,
    )


@router.get("/warehouses/{warehouse_id}", response_model=MerchantWarehouseSchema)
async def get_warehouse_by_ud(
    warehouse_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    warehouse = get_merchant_warehouse_by_id(
        db=db, id=warehouse_id, merchant_id=merchant.id
    )

    saleor_warehouse_response = await saleor_service.client.get_warehouse_by_id(
        wh_id=warehouse.saleor_warehouse_id
    )

    if not saleor_warehouse_response.warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found.",
        )

    saleor_warehouse = saleor_warehouse_response.warehouse

    return MerchantWarehouseSchema(
        id=warehouse.id,
        saleor_warehouse_id=warehouse.saleor_warehouse_id,
        merchant_id=warehouse.merchant_id,
        address=AddressCustomerInputSchema.from_db_model(warehouse.address) if warehouse.address else None,
        warehouse=WarehouseSchema(
            id=saleor_warehouse.id,
            name=saleor_warehouse.name,
            slug=saleor_warehouse.slug
        ),
    )


@router.post("/warehouses", response_model=MerchantWarehouseSchema)
async def create_warehouse(
    request: CreateMerchantWarehouseSchema,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    city = city_controller.get_city_by_id(db=db, city_id=request.address.city_id)

    create_warehouse_response = await saleor_service.client.create_warehouse(
        input=WarehouseCreateInput(
            name=request.name,
            address=AddressInput(
                skipValidation=True,
                streetAddress1=request.address.address_line_1,
                streetAddress2=request.address.address_line_2,
                city=city.name.get("ru"),
                country="KZ",
            ),
        )
    )

    if create_warehouse_response.create_warehouse.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create warehouse: {create_warehouse_response.create_warehouse.errors}",
        )
    
    db_address = address_controller.create_address(
        db=db,
        address=request.address.model_dump()
    )

    warehouse = create_warehouse_response.create_warehouse.warehouse

    db_wh = create_db_merchant_warehouse(
        db=db, saleor_warehouse_id=warehouse.id, merchant_id=merchant.id, address_id=db_address.id
    )

    return MerchantWarehouseSchema(
        id=db_wh.id,
        saleor_warehouse_id=db_wh.saleor_warehouse_id,
        merchant_id=db_wh.merchant_id,
        address=AddressCustomerInputSchema.from_db_model(db_address),
        warehouse=WarehouseSchema(
            id=warehouse.id,
            name=warehouse.name,
            slug=warehouse.slug,
            saleor_warehouse_id=warehouse.id,
        ),
    )


@router.patch("/warehouses/{warehouse_id}")
async def update_warehouse(
    request: PatchMerchantWarehouseSchema,
    warehouse_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    warehouse = get_merchant_warehouse_by_id(
        db=db, id=warehouse_id, merchant_id=merchant.id
    )

    saleor_warehouse_response = await saleor_service.client.get_warehouse_by_id(
        wh_id=warehouse.saleor_warehouse_id
    )

    if not saleor_warehouse_response.warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found.",
        )

    saleor_warehouse = saleor_warehouse_response.warehouse

    if not request.name and not request.address:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No update data"
        )

    update_input = WarehouseUpdateInput()

    if request.name:
        update_input.name = request.name

    if request.address:
        address_update_model = request.address.update_db_model(warehouse.address)
        db.add(address_update_model)
        db.commit()
        db.refresh(warehouse.address)
        update_input.address = saleor_warehouse.address.model_dump()
        update_input.address.country = "KZ"
        if request.address.city_id:
            city = city_controller.get_city_by_id(
                db=db, city_id=request.address.city_id
            )
            city_name = city.name.get("ru")
            update_input.address.city = city_name
        update_input.address.street_address_1 = request.address.address_line_1
        update_input.address.street_address_2 = request.address.address_line_2

    update_warehouse_response = await saleor_service.client.update_warehouse(
        id=warehouse.saleor_warehouse_id, input=update_input
    )

    if update_warehouse_response.update_warehouse.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update warehouse: {update_warehouse_response.update_warehouse.errors}",
        )

    saleor_warehouse = update_warehouse_response.update_warehouse.warehouse

    


    return MerchantWarehouseSchema(
        id=warehouse.id,
        saleor_warehouse_id=warehouse.saleor_warehouse_id,
        merchant_id=warehouse.merchant_id,
        address=AddressCustomerInputSchema.from_db_model(warehouse.address),
        warehouse=WarehouseSchema(
            id=saleor_warehouse.id,
            name=saleor_warehouse.name,
            slug=saleor_warehouse.slug,
        ),
    )


@router.delete("/warehouses/{warehouse_id}", response_model=dict)
async def delete_warehouse(
    warehouse_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    warehouse = get_merchant_warehouse_by_id(
        db=db, id=warehouse_id, merchant_id=merchant.id
    )

    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found.",
        )

    delete_warehouse_response = await saleor_service.client.delete_warehouse_by_id(
        warehouse_id=warehouse.saleor_warehouse_id
    )

    if delete_warehouse_response.delete_warehouse.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete warehouse: {delete_warehouse_response.delete_warehouse.errors}",
        )
    
    del warehouse
    db.commit()
    

    return dict(message="Warehouse deleted successfully")


@router.get("/warehouses/{warehouse_id}/stocks")
async def list_warehouse_stocks(
    warehouse_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
    first: Optional[int] = Query(
        25, description="Returns the first n elements from the list."
    ),
    last: Optional[int] = Query(
        None, description="Returns the last n elements from the list."
    ),
    after: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come after the specified cursor.",
    ),
    before: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come before the specified cursor.",
    ),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    warehouse = get_merchant_warehouse_by_id(
        db=db, id=warehouse_id, merchant_id=merchant.id
    )

    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found.",
        )

    stocks_response = await saleor_service.client.get_warehouse_with_stocks(
        wh_id=warehouse.saleor_warehouse_id,
        first=first,
        last=last,
        after=after,
        before=before,
    )

    return stocks_response.warehouse.stocks.edges


@router.post("/warehouses/{warehouse_id}/stock")
async def create_warehouse_stock(
    warehouse_id: str,
    request: CreateProductStockSchema,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    warehouse = get_merchant_warehouse_by_id(
        db=db, id=warehouse_id, merchant_id=merchant.id
    )

    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found.",
        )

    create_stock_response = await saleor_service.client.add_variant_stock(
        variant_id=request.product_variant_id,
        stocks=[
            StockInput(
                warehouse=warehouse.saleor_warehouse_id, quantity=request.quantity
            )
        ],
    )

    if create_stock_response.product_variant_stocks_create.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create stock: {create_stock_response.product_variant_stocks_create.errors}",
        )

    return create_stock_response.product_variant_stocks_create.bulk_stock_errors


@router.get("/orders", response_model=CursorPageWithOutTotal[SaleorOrderSchema])
async def list_orders_for_merchant(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
    params: CursorParamsWithOutTotal = Depends(),
    first: Optional[int] = Query(
        25, description="Returns the first n elements from the list."
    ),
    last: Optional[int] = Query(
        None, description="Returns the last n elements from the list."
    ),
    after: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come after the specified cursor.",
    ),
    before: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come before the specified cursor.",
    ),
):
    """
    Получаем список заказов мерчанта с пагинацией.
    Возвращает только заказы, у которых есть соответствующие транзакции в БД
    """
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view orders.",
        )

    if not current_user.merchants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any merchant.",
        )

    merchant = current_user.merchants[0]
    try:
        order_filter = OrderFilterInput(metadata=[{"key": "merchant_id", "value": "6f183b52-2cbf-4961-9f5f-790a02e2eebc"}])

        order_response = await saleor_service.client.get_order_list(
            filter=order_filter,
            first=first,
            last=last,
            after=after,
            before=before
        )

        if not order_response.orders or not order_response.orders.edges:
            return CursorPageWithOutTotal.create(items=[], params=params)

        saleor_orders = [edge.node for edge in order_response.orders.edges]

        filtered_orders = list_orders_for_merchant_with_transactions(
            db=db,
            merchant_id="6f183b52-2cbf-4961-9f5f-790a02e2eebc",
            saleor_orders=saleor_orders
        )
        enriched_orders = enrich_orders_with_customers(
            db=db,
            merchant_id="6f183b52-2cbf-4961-9f5f-790a02e2eebc",
            saleor_orders=filtered_orders
        )

        return CursorPageWithOutTotal.create(items=enriched_orders, params=params)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch orders: {str(e)}",
        )

@router.get("/payment-methods", response_model=MerchantPaymentMethodPaginatedResponse)
async def list_payment_methods_for_merchant():
    pass


@router.patch(
    "/payment-methods/{payment_method_id}", response_model=MerchantPaymentMethodSchema
)
async def update_payment_method():
    pass


@router.get("/employees", response_model=EmployeeListSchema)
async def list_employees_for_merchant(
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can read employees.",
        )

    return EmployeeListSchema.from_models(current_user.merchants[0].employees)


@router.get("/employees/{employee_id}", response_model=BaseEmployeeSchema)
async def get_employee(
    employee_id: str, current_user: User = Depends(security.get_current_user)
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can read employees.",
        )
    employee = [
        emp for emp in current_user.merchants[0].employees if emp.id == employee_id
    ][0]
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There is no employee with this id",
        )

    return BaseEmployeeSchema.from_model(employee)


@router.post("/employee", response_model=BaseEmployeeSchema)
async def create_employee(
    request: EmployeeSimpleAddSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can add employees.",
        )
    new_user = user_controller.create_with_phone(db=db, phone_number=request.phone)
    new_user.is_merchant = True
    db.add(new_user)
    db.flush()
    db.refresh(new_user)

    # Create an EmployeeProfile instance from the request data
    employee_profile_data = {
        "user_id": new_user.id,
        "first_name": request.first_name,
        "last_name": request.last_name,
    }

    merchant_controller.create_employee_for_merchant(
        db=db, employee=employee_profile_data, merchant=current_user.merchants[0]
    )
    db.commit()
    db.refresh(current_user)
    return BaseEmployeeSchema.from_model(current_user)


@router.patch("/employee/{employee_id}", response_model=BaseEmployeeSchema)
async def update_employee(
    employee_id: str,
    request: EmployeeSimpleAddSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can update employees",
        )
    if not current_user.merchants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any merchant",
        )
    employee = [
        emp for emp in current_user.merchants[0].employees if emp.id == employee_id
    ][0]
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There is no employee with this id",
        )
    employee.phone_number = request.phone
    db.commit()
    db.refresh(employee)
    return BaseEmployeeSchema.from_model(employee)


@router.delete("/employee/{employee_id}", response_model=BaseEmployeeSchema)
async def delete_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can update employees",
        )
    if not current_user.merchants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with any merchant",
        )
    merchant = current_user.merchants[0]
    employee = [emp for emp in merchant.employees if emp.id == employee_id][0]
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="There is no employee with this id",
            )
    
    merchant.employees.remove(employee)
    db.add(merchant)
    db.commit()
    return BaseEmployeeSchema.from_model(employee)


@router.get("/categories", response_model=CategoryListSchema)
async def list_categories_for_merchant(
    current_user: User = Depends(security.get_current_user),
    first: Optional[int] = Query(
        25, description="Returns the first n elements from the list."
    ),
    last: Optional[int] = Query(
        None, description="Returns the last n elements from the list."
    ),
    after: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come after the specified cursor.",
    ),
    before: Optional[str] = Query(
        None,
        description="Returns the elements in the list that come before the specified cursor.",
    ),
    search: Optional[str] = Query(None, description="Search term for category name."),
    level: Optional[int] = Query(None, description="Filter by category level."),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view categories.",
        )

    where_filter = None
    if search:
        where_filter = CategoryWhereInput(search=search)

    categories_response = await saleor_service.client.display_avaiable_categories(
        first=first,
        last=last,
        after=after,
        before=before,
        where=where_filter,
        level=level,
    )

    page_info = categories_response.categories.page_info
    edges = categories_response.categories.edges
    total_count = categories_response.categories.total_count
    categories = [edge.node.model_dump() for edge in edges]
    return CategoryListSchema(
        items=categories,
        total_count=total_count,
        has_next_page=page_info.has_next_page,
        has_previous_page=page_info.has_previous_page,
        start=page_info.start_cursor,
        end=page_info.end_cursor,
    )


@router.post("/merchant-site", response_model=MerchantSiteSchema)
async def create_merchant_site(
    request: MerchantSiteCreateSchema,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can create merchant site.",
        )

    merchant = current_user.merchants[0]

    existing_site = merchant_site_controller.check_merchant_have_site(
        db=db, merchant_id=merchant.id
    )
    if existing_site:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Merchant already has a site.",
        )

    if merchant_site_controller.check_site_existance(
        db=db, preffix=request.site_preffix, suffix=request.site_suffix
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Site preffix or suffix already exists.",
        )

    merchant_site = merchant_site_controller.create_merchant_site(
        db=db, site=request, merchant_id=merchant.id
    )
    return MerchantSiteSchema(
        id=merchant_site.id,
        site_preffix=merchant_site.site_preffix,
        site_suffix=merchant_site.site_suffix,
        is_active=merchant_site.is_active,
        site_carousel_items=[
            MerchantSiteCarouselItemSchema(
                id=item.id,
                url=item.url,
                is_active=item.is_active,
                order=item.order,
            )
            for item in merchant_site.merchant_site_carousel_items
        ],
    )


@router.patch("/merchant-site", response_model=MerchantSiteSchema)
async def update_merchant_site(
    request: MerchantSiteUpdateSchema,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view merchant site.",
        )

    merchant = current_user.merchants[0]

    if merchant_site_controller.check_site_existance(
        db=db, preffix=request.site_preffix, suffix=request.site_suffix
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Site preffix or suffix already exists.",
        )

    merchant_site_db = merchant_site_controller.get_site_by_merchant_id(
        db=db, merchant_id=merchant.id
    )

    merchant_site = merchant_site_controller.update_merchant_site(
        db=db,
        site=MerchantSiteUpdateSchema(
            site_preffix=(
                request.site_preffix
                if request.site_preffix
                else merchant_site_db.site_preffix
            ),
            site_suffix=(
                request.site_suffix
                if request.site_suffix
                else merchant_site_db.site_suffix
            ),
            is_active=(
                request.is_active
                if request.is_active is not None
                else merchant_site_db.is_active
            ),
        ),
        site_id=merchant_site_db.id,
    )
    return MerchantSiteSchema(
        id=merchant_site.id,
        site_preffix=merchant_site.site_preffix,
        site_suffix=merchant_site.site_suffix,
        is_active=merchant_site.is_active,
        site_carousel_items=[
            MerchantSiteCarouselItemSchema(
                id=item.id,
                url=item.url,
                is_active=item.is_active,
                order=item.order,
            )
            for item in merchant_site.merchant_site_carousel_items
        ],
    )


@router.get("/merchant-site", response_model=MerchantSiteSchema)
async def get_merchant_site(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can create merchant site.",
        )

    merchant = current_user.merchants[0]

    existing_site = merchant_site_controller.check_merchant_have_site(
        db=db, merchant_id=merchant.id
    )
    if not existing_site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant does not have a site.",
        )

    merchant_site = merchant_site_controller.get_site_by_merchant_id(
        db=db, merchant_id=merchant.id
    )
    return MerchantSiteSchema(
        id=merchant_site.id,
        site_preffix=merchant_site.site_preffix,
        site_suffix=merchant_site.site_suffix,
        is_active=merchant_site.is_active,
        site_carousel_items=[
            MerchantSiteCarouselItemSchema(
                id=item.id,
                url=item.url,
                is_active=item.is_active,
                order=item.order,
            )
            for item in merchant_site.merchant_site_carousel_items
        ],
    )


@router.get("/shipping-zones", response_model=ShippingZonesModelListSchema)
async def get_merchant_shipping_zones(
    db: Session = Depends(get_db),
    current_user: User = Depends(security.get_current_user),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    shipping_zones = list_shipping_zones_for_merchant(db=db, merchant_id=merchant.id)

    total_count = len(shipping_zones)

    return ShippingZonesModelListSchema(
        items=[
            ShippingZoneSchema(
                id=zone.id,
                name=zone.name,
                saleor_shipping_zone_id=zone.saleor_shipping_zone_id,
                warehouses=[],
            )
            for zone in shipping_zones
        ],
        total_count=total_count,
        has_next_page=False,
        has_previous_page=False,
    )


@router.post("/shipping-zones", response_model=ShippingZoneSchema)
async def create_merchant_shipping_zone(
    request: CreateShippingZoneRequest,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    existing_zone = get_merchant_shipping_zone_by_name(
        db=db, merchant_id=merchant.id, shipping_zone_name=request.name
    )

    if existing_zone:
        return ShippingZoneSchema(
            id=existing_zone.id,
            name=existing_zone.name,
            saleor_shipping_zone_id=existing_zone.saleor_shipping_zone_id,
            warehouses=[
                WarehouseSchema(
                    id=warehouse.id,
                    name=warehouse.name,
                    slug=warehouse.slug,
                    saleor_warehouse_id=warehouse.saleor_warehouse_id,
                )
                for warehouse in existing_zone.warehouses
            ],
        )

    saleor_create_sz_response = (
        await saleor_service.client.create_shipping_zone_for_merchant(
            {"name": request.name, "countries": ["KZ"]}
        )
    )

    if saleor_create_sz_response.shipping_zone_create.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create shipping zone: {saleor_create_sz_response.shipping_zone_create.errors}",
        )

    shipping_zone_id = saleor_create_sz_response.shipping_zone_create.shipping_zone.id

    shipping_zone = add_shipping_zone_to_merchant(
        db=db,
        merchant=merchant,
        shipping_zone_id=shipping_zone_id,
        shipping_zone_name=request.name,
    )

    return ShippingZoneSchema(
        id=shipping_zone.id,
        name=shipping_zone.name,
        saleor_shipping_zone_id=shipping_zone.saleor_shipping_zone_id,
        warehouses=[],
    )


@router.patch("/shipping-zones/{shipping_zone_id}", response_model=ShippingZoneSchema)
async def update_merchant_shipping_zone(
    request: PatchShippingZoneRequest,
    shipping_zone_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    shipping_zone = get_merchant_shipping_zone_by_id(
        db=db, id=shipping_zone_id, merchant_id=merchant.id
    )

    if not shipping_zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipping zone not found.",
        )

    if request.name:
        shipping_zone.name = request.name

    wherehouses_entities = []

    if request.warehouses:
        for wh in request.warehouses:
            entry = get_merchant_warehouse_by_id(db=db, id=wh, merchant_id=merchant.id)
            if not entry:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Warehouses to add not found",
                )
            wherehouses_entities.append(entry)

    shipping_zone.warehouses = wherehouses_entities
    update_channel_response = await saleor_service.client.update_channel(
        channel_id=settings.LINK_SALEOR_CHANNEL_ID,
        channel_update_input=ChannelUpdateInput(
            addWarehouses=(
                [wh.saleor_warehouse_id for wh in wherehouses_entities]
                if len(wherehouses_entities) > 0
                else []
            ),
            addShippingZones=[shipping_zone.saleor_shipping_zone_id],
        ),
    )

    if update_channel_response.channel_update.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update shipping zone: {update_channel_response.channel_update.errors}",
        )

    # make request for saleor
    saleor_update_sz_response = await saleor_service.client.update_shipping_zone(
        shipping_zone_id=shipping_zone.saleor_shipping_zone_id,
        name=request.name,
        add_warehouses=[whe.saleor_warehouse_id for whe in wherehouses_entities],
        remove_warehouses=[],
    )
    if saleor_update_sz_response.shipping_zone_update.errors:
        print(saleor_update_sz_response.shipping_zone_update.errors)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update shipping zone: {saleor_update_sz_response.shipping_zone_update.errors}",
        )

    db.add(shipping_zone)
    db.commit()
    db.refresh(shipping_zone)

    return ShippingZoneSchema(
        id=shipping_zone.id,
        name=shipping_zone.name,
        saleor_shipping_zone_id=shipping_zone.saleor_shipping_zone_id,
        warehouses=[
            WarehouseSchema(id=warehouse.saleor_warehouse_id)
            for warehouse in shipping_zone.warehouses
        ],
        shipping_methods=[],
    )


@router.delete("/shipping-zones/{shipping_zone_id}", response_model=dict)
async def delete_merchant_shipping_zone(
    shipping_zone_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    shipping_zone = get_merchant_shipping_zone_by_id(
        db=db, id=shipping_zone_id, merchant_id=merchant.id
    )

    if not shipping_zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipping zone not found.",
        )

    saleor_delete_sz_response = await saleor_service.client.delete_shipping_zone_by_id(
        shipping_zone_id=shipping_zone.saleor_shipping_zone_id
    )

    if saleor_delete_sz_response.shipping_zone_delete.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete shipping zone: {saleor_delete_sz_response.shipping_zone_delete.errors}",
        )

    db.delete(shipping_zone)
    db.commit()
    return dict(message="Shipping zone deleted successfully")


@router.get("/shipping-zones/{shipping_zone_id}", response_model=FullShippingZoneSchema)
async def get_merchant_shipping_zone(
    shipping_zone_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    shipping_zone = get_merchant_shipping_zone_by_id(
        db=db, id=shipping_zone_id, merchant_id=merchant.id
    )

    if not shipping_zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipping zone not found.",
        )
    shipping_zone_response = await saleor_service.client.get_shipping_zone_info_by_id(
        sz_id=shipping_zone.saleor_shipping_zone_id
    )

    return FullShippingZoneSchema(
        id=shipping_zone.id,
        name=shipping_zone.name,
        saleor_shipping_zone_id=shipping_zone.saleor_shipping_zone_id,
        warehouses=(
            [
                WarehouseSchema(
                    id=warehouse.id, name=warehouse.name, slug=warehouse.slug
                )
                for warehouse in shipping_zone_response.shipping_zone.warehouses
            ]
            if shipping_zone_response.shipping_zone.warehouses
            else []
        ),
        shipping_methods=[
            ShippingMethodSchema(
                shipping_id=method.id,
                name=method.name,
                maximum_delivery_days=method.maximum_delivery_days,
                minimum_delivery_days=method.minimum_delivery_days,
                pricing_by_channels=(
                    [
                        ShippingMethodPriceSchema(
                            channel_id=channel.channel.id,
                            channel_name=channel.channel.name,
                            price=channel.price.amount if channel.price else None,
                            maximum_order_price=(
                                channel.maximum_order_price.amount
                                if channel.maximum_order_price
                                else None
                            ),
                            minimum_order_price=(
                                channel.minimum_order_price.amount
                                if channel.minimum_order_price
                                else None
                            ),
                        )
                        for channel in method.channel_listings
                    ]
                    if method.channel_listings
                    else []
                ),
            )
            for method in shipping_zone_response.shipping_zone.shipping_methods
        ],
    )


@router.post(
    "/shipping-zones/{shipping_zone_id}/add-shipping-method",
    response_model=ShippingMethodSchema,
)
async def add_shipping_method_to_shipping_zone(
    request: AddShippingMethodToShippingZoneRequest,
    shipping_zone_id: str,
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view shipping zones.",
        )

    merchant = current_user.merchants[0]

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Merchant not found.",
        )

    shipping_zone = get_merchant_shipping_zone_by_id(
        db=db, id=shipping_zone_id, merchant_id=merchant.id
    )

    if not shipping_zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipping zone not found.",
        )
    shipping_price_response = await saleor_service.client.create_shipping_price(
        sz_id=shipping_zone.saleor_shipping_zone_id,
        name=request.name,
        maximum_delivery_days=request.maximum_delivery_days,
        minimum_delivery_days=request.minimum_delivery_days,
    )

    if shipping_price_response.shipping_price_create.errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create shipping price: {shipping_price_response.shipping_price_create.errors}",
        )

    shipping_method_id = (
        shipping_price_response.shipping_price_create.shipping_method.id
    )

    add_shipping_method_to_channel_response = (
        await saleor_service.client.add_shipping_method_to_channel(
            ship_met_id=shipping_method_id,
            shipping_method_channels_list=[
                ShippingMethodChannelListingAddInput(
                    channelId=settings.LINK_SALEOR_CHANNEL_ID,
                    price=request.price,
                    maximumOrderPrice=request.maximum_order_price,
                    minimumOrderPrice=request.minimum_order_price,
                )
            ],
        )
    )

    if (
        add_shipping_method_to_channel_response.shipping_method_channel_listing_update.errors
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set up prices for channel: {add_shipping_method_to_channel_response.shipping_method_channel_listing_update.errors}",
        )

    shipping_method = (
        add_shipping_method_to_channel_response.shipping_method_channel_listing_update.shipping_method
    )

    return ShippingMethodSchema(
        shipping_id=shipping_method.id,
        name=shipping_method.name,
        maximum_delivery_days=shipping_method.maximum_delivery_days,
        minimum_delivery_days=shipping_method.minimum_delivery_days,
        pricing_by_channels=(
            [
                ShippingMethodPriceSchema(
                    channel_id=channel.channel.id,
                    channel_name=channel.channel.name,
                    price=channel.price.amount if channel.price else None,
                    maximum_order_price=(
                        channel.maximum_order_price.amount
                        if channel.maximum_order_price
                        else None
                    ),
                    minimum_order_price=(
                        channel.minimum_order_price.amount
                        if channel.minimum_order_price
                        else None
                    ),
                )
                for channel in shipping_method.channel_listings
            ]
            if shipping_method.channel_listings
            else []
        ),
    )


@router.post("/mfo-registration", response_model=dict)
async def mfo_registration(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view merchant site.",
        )

    merchant = current_user.merchants[0]
    print(merchant)
    try:
        return await mfoService.register_merchant(
            bin=merchant.bin,
            name=merchant.legal_name,
            phone=current_user.phone_number,
            account=merchant.id,
        )
    except Exception as e:
        raise e


@router.post("/terminal-registration", response_model=dict)
async def terminal_registration(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view merchant site.",
        )

    merchant = current_user.merchants[0]

    try:
        response = await freedom_terminal.register_terminal(merchant.id)
        if response["message"] == "CONNECTED":
            merchant.mcc = response["mcc"]
            merchant.mid = response["mid"]
            merchant.tid = response["tid"]
            merchant.oked = response["oked"]
            db.commit()
            return response
        if response["message"] == "IN_PROGRESS":
            return None
    except Exception as e:
        raise e


@router.post("/obtaining-period", response_model=list[dict])
async def period(
    current_user: User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants can view merchant site.",
        )

    merchant = current_user.merchants[0]

    try:
        periods = await mfoService.generate_periods(bin=merchant.bin)
        merchant_controller.add_mfo_periods(
            db, payment_methods=merchant.merchant_payment_methods, periods=periods
        )
        return periods
    except StopIteration:
        raise Exception("Installment payment method not found")
