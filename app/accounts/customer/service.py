from datetime import datetime

from fastapi import HTTPException

from sqlalchemy import (
    select,
    desc,
    or_,
    and_,
    func,
)

from sqlalchemy.exc import IntegrityError

from app.accounts.branch.model import Branch
from app.accounts.client.model import Client
from app.accounts.customer.model import Customer
from app.accounts.customer.schema import (
    CustomerCreate,
    CustomerUpdate,
)
from app.accounts.deps import UserRole


# =========================================================
# CREATE CUSTOMER FROM CUSTOMER SCREEN
# =========================================================

async def create_customer_service(
    payload: CustomerCreate,
    db,
):
    branch = await db.get(
        Branch,
        payload.branch_id,
    )

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    name = (
        payload.name.strip()
        if payload.name and payload.name.strip()
        else None
    )

    phone = (
        payload.phone.strip()
        if payload.phone and payload.phone.strip()
        else None
    )

    email = (
        payload.email.strip().lower()
        if payload.email and payload.email.strip()
        else None
    )

    # -----------------------------------------------------
    # Customer screen requires:
    # name + (phone OR email)
    # -----------------------------------------------------

    if not name:
        raise HTTPException(
            status_code=422,
            detail="Customer name is required.",
        )

    if not phone and not email:
        raise HTTPException(
            status_code=422,
            detail="Either phone or email is required.",
        )

    # -----------------------------------------------------
    # Check existing customer
    # -----------------------------------------------------

    existing = await find_existing_customer(
        db=db,
        client_id=branch.client_id,
        name=name,
        phone=phone,
        email=email,
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Customer already exists "
                f"(customer_id={existing.id})."
            ),
        )

    # -----------------------------------------------------
    # Create
    # -----------------------------------------------------

    customer = Customer(
        name=name,
        phone=phone,
        email=email,
        address=payload.address,
        gender=payload.gender,
        dob=payload.dob,
        anniversary=payload.anniversary,
        profile_photo=payload.profile_photo,
        customer_source=payload.customer_source or "Walk-In",
        customer_type=payload.customer_type or "Regular",
        preferred_language=(
            payload.preferred_language or "English"
        ),
        preferred_contact=(
            payload.preferred_contact or "WhatsApp"
        ),
        marketing_opt_in=(
            payload.marketing_opt_in
            if payload.marketing_opt_in is not None
            else True
        ),
        remarks=payload.remarks,
        branch_id=branch.id,
        branch_name=branch.name,
        client_id=branch.client_id,
    )

    db.add(customer)

    await db.commit()

    await db.refresh(customer)

    return customer


# =========================================================
# FIND EXISTING CUSTOMER
# =========================================================

async def find_existing_customer(
    db,
    client_id: int,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
):
    """
    Customer matching rule:

        name + phone
            OR
        name + email

    Phone alone is NOT enough.
    Email alone is NOT enough.
    Name alone is NOT enough.
    """

    name = (
        name.strip()
        if name and name.strip()
        else None
    )

    phone = (
        phone.strip()
        if phone and phone.strip()
        else None
    )

    email = (
        email.strip().lower()
        if email and email.strip()
        else None
    )

    if not name:
        return None

    # -----------------------------------------------------
    # NAME + PHONE
    # -----------------------------------------------------

    if phone:
        customer = await db.scalar(
            select(Customer).where(
                Customer.client_id == client_id,
                func.lower(Customer.name)
                == name.lower(),
                Customer.phone == phone,
            )
        )

        if customer:
            return customer

    # -----------------------------------------------------
    # NAME + EMAIL
    # -----------------------------------------------------

    if email:
        customer = await db.scalar(
            select(Customer).where(
                Customer.client_id == client_id,
                func.lower(Customer.name)
                == name.lower(),
                func.lower(Customer.email)
                == email,
            )
        )

        if customer:
            return customer

    return None


# =========================================================
# FIND OR CREATE CUSTOMER FROM ORDER
# =========================================================

async def find_or_create_customer(
    db,
    *,
    client_id: int,
    branch_id: int,
    branch_name: str,
    name: str | None,
    phone: str | None = None,
    email: str | None = None,
):
    """
    IMPORTANT BUSINESS RULE:

    Customer is created ONLY when:

        name + phone
        OR
        name + email

    Otherwise:

        Guest

    Guest does NOT create:
        - Customer record
        - CustomerVisitHistory record

    Returns:

        (customer, created)

    Guest:
        (None, False)

    Existing customer:
        (Customer, False)

    New customer:
        (Customer, True)
    """

    # -----------------------------------------------------
    # CLEAN DATA
    # -----------------------------------------------------

    name = (
        name.strip()
        if name and name.strip()
        else None
    )

    phone = (
        phone.strip()
        if phone and phone.strip()
        else None
    )

    email = (
        email.strip().lower()
        if email and email.strip()
        else None
    )

    # -----------------------------------------------------
    # GUEST CHECK
    # -----------------------------------------------------

    # Name + phone/email required.
    #
    # If this condition fails:
    # NEVER create Customer.
    #
    if not name or (not phone and not email):
        return None, False

    # -----------------------------------------------------
    # FIND EXISTING CUSTOMER
    # -----------------------------------------------------

    customer = await find_existing_customer(
        db=db,
        client_id=client_id,
        name=name,
        phone=phone,
        email=email,
    )

    if customer:
        return customer, False

    # -----------------------------------------------------
    # CREATE CUSTOMER
    # -----------------------------------------------------

    customer = Customer(
        client_id=client_id,
        branch_id=branch_id,
        branch_name=branch_name,
        name=name,
        phone=phone,
        email=email,
    )

    db.add(customer)

    try:
        await db.flush()

    except IntegrityError:
        await db.rollback()

        # Try finding again in case another request
        # created the customer concurrently.
        customer = await find_existing_customer(
            db=db,
            client_id=client_id,
            name=name,
            phone=phone,
            email=email,
        )

        if customer:
            return customer, False

        raise

    return customer, True


# =========================================================
# GET CUSTOMERS
# =========================================================

async def get_customers_service(
    db,
    current,
    client_id=None,
    branch_id=None,
):
    role = current["role"]
    user = current["user"]

    query = select(Customer)

    if role == UserRole.SUPER_ADMIN:

        if client_id:
            query = query.where(
                Customer.client_id == client_id
            )

    elif role == UserRole.PARTNER:

        query = (
            query.join(
                Client,
                Client.id == Customer.client_id,
            )
            .where(
                Client.partner_id == user.id,
            )
        )

        if client_id:
            query = query.where(
                Customer.client_id == client_id
            )

    elif role == UserRole.CLIENT:

        query = query.where(
            Customer.client_id == user.id
        )

    elif role == UserRole.STAFF:

        query = query.where(
            Customer.client_id == user.client_id
        )

    else:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    if branch_id:
        query = query.where(
            Customer.branch_id == branch_id
        )

    query = query.order_by(
        desc(Customer.created_at)
    )

    result = await db.execute(query)

    return result.scalars().all()


# =========================================================
# UPDATE CUSTOMER
# =========================================================

async def update_customer_service(
    customer_id: int,
    payload: CustomerUpdate,
    db,
):
    customer = await db.get(
        Customer,
        customer_id,
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    # -----------------------------------------------------
    # NORMALIZE PHONE
    # -----------------------------------------------------

    if "phone" in update_data:

        phone = update_data["phone"]

        update_data["phone"] = (
            phone.strip()
            if phone and phone.strip()
            else None
        )

    # -----------------------------------------------------
    # NORMALIZE EMAIL
    # -----------------------------------------------------

    if "email" in update_data:

        email = update_data["email"]

        update_data["email"] = (
            email.strip().lower()
            if email and email.strip()
            else None
        )

    # -----------------------------------------------------
    # NORMALIZE NAME
    # -----------------------------------------------------

    if "name" in update_data:

        name = update_data["name"]

        update_data["name"] = (
            name.strip()
            if name and name.strip()
            else None
        )

    # -----------------------------------------------------
    # Validate customer identity
    #
    # Customer must always have:
    # name + phone/email
    # -----------------------------------------------------

    final_name = update_data.get(
        "name",
        customer.name,
    )

    final_phone = update_data.get(
        "phone",
        customer.phone,
    )

    final_email = update_data.get(
        "email",
        customer.email,
    )

    if not final_name:
        raise HTTPException(
            status_code=422,
            detail="Customer name is required.",
        )

    if not final_phone and not final_email:
        raise HTTPException(
            status_code=422,
            detail=(
                "Customer must have either "
                "phone or email."
            ),
        )

    # -----------------------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------------------

    if (
        final_name
        and final_phone
    ):

        result = await db.execute(
            select(Customer).where(
                Customer.client_id
                == customer.client_id,

                func.lower(Customer.name)
                == final_name.lower(),

                Customer.phone
                == final_phone,

                Customer.id
                != customer.id,
            )
        )

        duplicate = result.scalar_one_or_none()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Customer with same "
                    "name and phone already exists."
                ),
            )

    if (
        final_name
        and final_email
    ):

        result = await db.execute(
            select(Customer).where(
                Customer.client_id
                == customer.client_id,

                func.lower(Customer.name)
                == final_name.lower(),

                func.lower(Customer.email)
                == final_email.lower(),

                Customer.id
                != customer.id,
            )
        )

        duplicate = result.scalar_one_or_none()

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Customer with same "
                    "name and email already exists."
                ),
            )

    # -----------------------------------------------------
    # BRANCH UPDATE
    # -----------------------------------------------------

    if "branch_id" in update_data:

        new_branch_id = update_data["branch_id"]

        if new_branch_id != customer.branch_id:

            branch = await db.get(
                Branch,
                new_branch_id,
            )

            if not branch:
                raise HTTPException(
                    status_code=404,
                    detail="Branch not found",
                )

            customer.branch_id = branch.id
            customer.branch_name = branch.name
            customer.client_id = branch.client_id

    # -----------------------------------------------------
    # APPLY UPDATE
    # -----------------------------------------------------

    for key, value in update_data.items():

        if key != "branch_id":
            setattr(
                customer,
                key,
                value,
            )

    await db.commit()

    await db.refresh(customer)

    return customer


# =========================================================
# DELETE CUSTOMER
# =========================================================

async def delete_customer_service(
    customer_id: int,
    db,
):
    customer = await db.get(
        Customer,
        customer_id,
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found",
        )

    await db.delete(customer)

    await db.commit()

    return {
        "message": "Customer deleted"
    }


# =========================================================
# ALL BRANCHES
# =========================================================

async def get_customers_all_branches(
    db,
    client_id: int,
):
    branches_result = await db.execute(
        select(Branch).where(
            Branch.client_id == client_id
        )
    )

    branches = branches_result.scalars().all()

    if not branches:
        return {
            "total_customers": 0,
            "branches": [],
        }

    customers_result = await db.execute(
        select(Customer).where(
            Customer.client_id == client_id
        )
    )

    customers = customers_result.scalars().all()

    response = {
        "total_customers": len(customers),
        "branches": [],
    }

    for branch in branches:

        branch_customers = [
            customer
            for customer in customers
            if customer.branch_id == branch.id
        ]

        response["branches"].append(
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "total_customers": len(
                    branch_customers
                ),
                "customers": [
                    {
                        "id": customer.id,
                        "name": customer.name,
                        "phone": customer.phone,
                        "email": customer.email,
                        "address": customer.address,
                        "created_at": customer.created_at,
                    }
                    for customer in branch_customers
                ],
            }
        )

    return response


# =========================================================
# RECALCULATE CRM
# =========================================================

async def recalculate_customer_crm(
    db,
    customer_id: int,
    branch_id: int | None = None,
):
    """
    Recalculate CRM only for REAL customers.

    Guest orders never reach this function because
    guests have no Customer record.
    """

    from app.accounts.crm.customer_history.model import (
        CustomerVisitHistory,
    )

    from app.accounts.crm.rank_rules.model import (
        CRMBranchRankRule,
    )

    from app.accounts.order.model import Order

    customer = await db.get(
        Customer,
        customer_id,
    )

    if not customer:
        return None

    target_branch_id = (
        branch_id
        or customer.branch_id
    )

    # -----------------------------------------------------
    # VISIT HISTORY
    # -----------------------------------------------------

    stmt = (
        select(CustomerVisitHistory)
        .outerjoin(
            Order,
            CustomerVisitHistory.order_id
            == Order.id,
        )
        .where(
            CustomerVisitHistory.customer_id
            == customer_id,

            or_(
                CustomerVisitHistory.order_id.is_(None),

                func.lower(Order.status)
                != "cancelled",
            ),
        )
        .order_by(
            CustomerVisitHistory.visit_date.asc()
        )
    )

    result = await db.execute(stmt)

    visits = result.scalars().all()

    # -----------------------------------------------------
    # CALCULATE
    # -----------------------------------------------------

    total_visits = len(visits)

    total_spend = round(
        sum(
            float(
                visit.total_amount or 0
            )
            for visit in visits
        ),
        2,
    )

    customer.total_visits = total_visits

    customer.total_orders = total_visits

    customer.total_spend = total_spend

    if total_visits > 0:

        customer.average_order_value = round(
            total_spend / total_visits,
            2,
        )

        last_visit = visits[-1]

        customer.last_visit_at = (
            last_visit.visit_date
        )

        customer.last_order_amount = float(
            last_visit.total_amount or 0
        )

        if last_visit.order_id:
            customer.last_order_id = (
                last_visit.order_id
            )

        if visits[0].visit_date:
            customer.first_visit_at = (
                visits[0].visit_date
            )

    else:

        customer.average_order_value = 0

        customer.last_order_amount = 0

    # -----------------------------------------------------
    # RANK
    # -----------------------------------------------------

    if target_branch_id:

        rule_stmt = select(
            CRMBranchRankRule
        ).where(
            CRMBranchRankRule.branch_id
            == target_branch_id,

            CRMBranchRankRule.is_active
            == True,
        )

        rule_result = await db.execute(
            rule_stmt
        )

        rule = rule_result.scalar_one_or_none()

        if rule:
            gold_min = float(rule.gold_min or 0)
            silver_min = float(rule.silver_min or 0)

            if total_spend >= gold_min:
                new_rank = "Gold"
            elif total_spend >= silver_min:
                new_rank = "Silver"
            else:
                new_rank = "Bronze"

            customer.current_rank = new_rank

            # Sync customer.loyalty_points from CustomerLoyaltyAccount balance (redemption-safe)
            from app.accounts.crm.loyalty.model import CustomerLoyaltyAccount
            account_stmt = select(CustomerLoyaltyAccount).where(
                CustomerLoyaltyAccount.customer_id == customer.id
            )
            account_res = await db.execute(account_stmt)
            loyalty_acc = account_res.scalar_one_or_none()
            if loyalty_acc:
                customer.loyalty_points = float(loyalty_acc.current_points_balance or 0.0)

    await db.flush()

    return customer