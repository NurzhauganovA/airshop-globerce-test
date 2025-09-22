from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.controllers.base import BaseController
from app.models.internal_model import MerchantPaymentMethod
from app.models.transaction_models import (
    Transaction,
    CardRequest,
    LoanRequest,
    LoanOffer,
)
from app.schemas.loanrequest_schemas import (
    LoanRequestCreateSchema,
    LoanRequestUpdateSchema,
    LoanOfferCreateSchema,
    LoanOfferUpdateSchema,
)


class LoanRequestController(
    BaseController[LoanRequest, LoanRequestCreateSchema, LoanRequestUpdateSchema]
): ...


class LoanOfferController(
    BaseController[LoanOffer, LoanOfferCreateSchema, LoanOfferUpdateSchema]
): ...


load_request_controller = LoanRequestController(LoanRequest)
load_offer_controller = LoanOfferController(LoanOffer)


def get_transaction_by_order_id(
    db: Session, *, saleor_order_id: str
) -> Optional[Transaction]:
    """
    Retrieves a transaction by its associated Saleor order ID.
    """
    return (
        db.query(Transaction)
        .filter(Transaction.saleor_order_id == saleor_order_id)
        .first()
    )


def create_transaction(
    db: Session,
    *,
    saleor_order_id: str,
    amount: Decimal,
) -> Transaction:
    """
    Creates a new transaction for a Saleor order.
    If a transaction for this order already exists, it returns the existing one.
    """
    existing_transaction = get_transaction_by_order_id(
        db, saleor_order_id=saleor_order_id
    )
    if existing_transaction:
        return existing_transaction

    db_transaction = Transaction(
        saleor_order_id=saleor_order_id,
        amount=amount,
        currency="KZT",
        status="NEW",
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


def set_transaction_payment_type(
    db: Session, *, transaction: Transaction, payment_method_id: str
) -> Transaction:
    """
    Sets the payment method for a transaction.
    """
    transaction.payment_method_id = payment_method_id
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def update_transaction_payment_type(
    db: Session, *, transaction: Transaction, new_payment_method_id: str
) -> Transaction:
    """
    Updates the payment method for a transaction.
    This might involve cleaning up old payment-type-specific requests if the base type changes.
    """
    # Eagerly load the base_method to avoid extra queries
    old_pm = (
        db.query(MerchantPaymentMethod)
        .options(joinedload(MerchantPaymentMethod.base_method))
        .get(transaction.payment_method_id)
    )
    new_pm = (
        db.query(MerchantPaymentMethod)
        .options(joinedload(MerchantPaymentMethod.base_method))
        .get(new_payment_method_id)
    )

    if old_pm and new_pm and old_pm.base_method.type != new_pm.base_method.type:
        if old_pm.base_method.type == "CARD":
            for req in transaction.card_requests:
                db.delete(req)
        elif old_pm.base_method.type == "LOAN":
            for req in transaction.loan_requests:
                for offer in req.loan_offers:
                    db.delete(offer)
                db.delete(req)

    transaction.payment_method_id = new_payment_method_id
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def create_card_payment_request(
    db: Session, *, transaction: Transaction
) -> CardRequest:
    """
    Creates a card payment request for a transaction.
    Assumes the transaction's payment method is of type 'CARD'.
    If a request already exists, it returns the existing one.
    """
    if transaction.card_requests:
        return transaction.card_requests[0]

    card_request = CardRequest(
        transaction_id=transaction.id,
        status="PENDING",
    )
    db.add(card_request)
    transaction.status = "IN_PROGRESS"
    db.add(transaction)
    db.commit()
    db.refresh(card_request)
    return card_request


def create_loan_payment_request(
    db: Session, *, transaction: Transaction, iin: str, mobile_phone: str
) -> LoanRequest:
    """
    Creates or updates a loan payment request for a transaction with the given IIN.
    Assumes the transaction's payment method is of type 'LOAN'.
    """
    if transaction.loan_requests:
        existing_request = transaction.loan_requests[0]
        if existing_request.iin != iin:
            existing_request.iin = iin
        if existing_request.mobile_phone != mobile_phone:
            existing_request.mobile_phone = mobile_phone
        db.add(existing_request)
        db.commit()
        db.refresh(existing_request)

        return existing_request

    loan_request = LoanRequest(
        transaction_id=transaction.id,
        status="PENDING",
        iin=iin,
        mobile_phone=mobile_phone,
    )
    db.add(loan_request)
    transaction.status = "IN_PROGRESS"
    db.add(transaction)
    db.commit()
    db.refresh(loan_request)
    return loan_request


def get_loan_offers(db: Session, *, loan_request_id: str) -> List[LoanOffer]:
    """
    Retrieves loan offers for a given loan request ID.
    """
    loan_request = db.query(LoanRequest).get(loan_request_id)
    if not loan_request:
        return []
    return loan_request.loan_offers


def set_loan_offer(
    db: Session, *, loan_request_id: str, offer_id: str
) -> Optional[LoanOffer]:
    """
    Sets a specific loan offer as suitable for the loan request.
    Unsets other offers for the same request.
    """
    loan_request = db.query(LoanRequest).get(loan_request_id)
    if not loan_request:
        return None

    chosen_offer = None
    for offer in loan_request.loan_offers:
        if offer.id == offer_id:
            offer.suitable = True
            chosen_offer = offer
        else:
            offer.suitable = False
        db.add(offer)

    if chosen_offer:
        loan_request.status = "OFFER_SELECTED"
        db.add(loan_request)
        db.commit()
        db.refresh(chosen_offer)
        return chosen_offer

    # If offer_id was not found, commit any changes to `suitable=False`
    db.commit()
    return None


def set_new_status(
    db: Session, *, transaction: Transaction, new_status: str
) -> Transaction:
    """
    Sets the status of a transaction.
    """
    transaction.status = new_status
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_card_request_by_id(db: Session, *, card_request_id: str) -> CardRequest | None:
    """
    Retrieves a card request by its ID.
    """
    return db.query(CardRequest).get(card_request_id)


def get_transaction_by_id(db: Session, *, transaction_id: str) -> Transaction | None:
    """
    Retrieves a transaction by its ID.
    """
    return db.query(Transaction).get(transaction_id)


def get_loan_request_by_mfo_uuid(db: Session, *, uuid: str) -> LoanRequest | None:
    """
    get loan request by mfo uuid
    """
    return db.query(LoanRequest).filter(LoanRequest.mfo_uuid == uuid).first()


def get_loan_request_by_id(db: Session, *, loan_request_id: str) -> LoanRequest | None:
    """
    get loan request by id
    """
    return db.query(LoanRequest).get(loan_request_id)
