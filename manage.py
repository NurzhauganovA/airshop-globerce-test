import os
import datetime
import uuid

from faker import Faker
import click
from sqlalchemy import create_engine
from psycopg2.extras import NumericRange
from sqlalchemy.orm import sessionmaker

from app.core import security
from app.core.database import (
    Base,
)  # Assuming this is where your Base and engine are configured
from app.models.internal_model import (
    User,
    Merchant,
    Country,
    City,
    Address,
    BasePaymentMethod,
)  # Import your models


fake = Faker()

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://user:password@host:port/database"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@click.group()
def cli():
    """Airshop management script."""
    pass


@cli.command()
def create_db():
    """Creates the database tables."""
    Base.metadata.create_all(bind=engine)
    click.echo("Database tables created.")


@cli.command()
def drop_db():
    """Drops the database tables."""
    Base.metadata.drop_all(bind=engine)
    click.echo("Database tables dropped.")


@cli.command()
def populate_data():
    """Populates the database with demo data."""
    db = SessionLocal()
    try:
        # Create sample data
        country_kz = Country(
            id=str(uuid.uuid4()),
            name={"en": "Kazakhstan", "kk": "Қазақстан", "ru": "Казахстан"},
            currency_code="KZT",
            postal_codes_range=[{"start": "010000", "end": "090000"}],
        )
        db.add(country_kz)
        db.commit()

        city_almaty = City(
            id=str(uuid.uuid4()),
            name={"en": "Almaty", "kk": "Алматы", "ru": "Алматы"},
            country_id=country_kz.id,
        )
        db.add(city_almaty)
        db.commit()

        user1 = User(
            id=str(uuid.uuid4()),
            phone_number=fake.phone_number(),
            password_hash=security.get_password_hash("password123"),
            username=fake.user_name(),
            email=fake.email(),
            is_merchant=True,
            is_admin=False,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(user1)
        db.commit()

        merchant1 = Merchant(
            id=str(uuid.uuid4()),
            legal_name=fake.company(),
            bin="123456789012",
            iban="123456789012",
            mid=None,
            mcc=None,
            tid=None,
            oked=None,
            is_active=True,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(merchant1)
        db.commit()

        # Associate the user with the merchant
        user1.merchants.append(merchant1)
        db.commit()

        address1 = Address(
            id=str(uuid.uuid4()),
            name="Office Address",
            contact_phone=fake.phone_number(),
            address_line_1=fake.street_address(),
            address_line_2=fake.secondary_address(),
            address_line_3=None,
            country_id=country_kz.id,
            city_id=city_almaty.id,
            creator_id=user1.id,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            modified_at=datetime.datetime.now(datetime.timezone.utc),
        )
        db.add(address1)
        db.commit()

        click.echo("Demo data added successfully!")

    except Exception as e:
        db.rollback()
        click.echo(f"An error occurred: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--count", default=1, help="Number of fake records to create.")
def populate_fake_data(count):
    """Populates the database with fake data using Faker."""
    db = SessionLocal()
    try:
        for _ in range(count):
            # Example: Create a fake user
            fake_user = User(
                id=str(uuid.uuid4()),
                phone_number=fake.phone_number(),
                password_hash=security.get_password_hash(fake.password()),
                username=fake.user_name(),
                email=fake.email(),
            )
            db.add(fake_user)
        db.commit()
        click.echo(f"{count} fake records added successfully!")
    except Exception as e:
        db.rollback()
        click.echo(f"An error occurred: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--username", prompt=True, help="Username for the technical user.")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Password for the technical user.",
)
def create_technical_user(username, password):
    """Creates a new technical user."""
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            click.echo(f"User with username '{username}' already exists.")
            return

        password_hash = security.get_password_hash(password)
        technical_user = User(
            username=username, password_hash=password_hash, is_technical=True
        )
        db.add(technical_user)
        db.commit()
        click.echo(f"Technical user '{username}' created successfully!")
    except Exception as e:
        db.rollback()
        click.echo(f"An error occurred: {e}")
    finally:
        db.close()


@cli.command()
@click.option("--username", prompt=True, help="The username for the new user.")
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="The password for the new user.",
)
@click.option("--is-admin", is_flag=True, default=False, help="Set user as an admin.")
@click.option(
    "--is-technical", is_flag=True, default=False, help="Set user as a technical user."
)
def create_user(username, password, is_admin, is_technical):
    """Creates a new user with specified roles."""
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            click.echo(f"User with username '{username}' already exists.")
            return

        password_hash = security.get_password_hash(password)
        new_user = User(
            username=username,
            password_hash=password_hash,
            is_admin=is_admin,
            is_technical=is_technical,
        )
        db.add(new_user)
        db.commit()

        roles = [r for r, s in [("admin", is_admin), ("technical", is_technical)] if s]
        role_str = f" with roles: {', '.join(roles)}" if roles else ""
        click.echo(f"User '{username}' created successfully{role_str}!")

    except Exception as e:
        db.rollback()
        click.echo(f"An error occurred: {e}")
    finally:
        db.close()


@cli.command()
def populate_base_payment_methods():
    """Populates the BasePaymentMethod table with initial data."""
    db = SessionLocal()
    try:
        if db.query(BasePaymentMethod).first():
            click.echo("BasePaymentMethod table already has data. Aborting.")
            return

        payment_methods_to_add = [
            BasePaymentMethod(type="CARD", enabled=True),
            BasePaymentMethod(
                type="LOAN",
                loan_type="CREDIT",
                loan_period_range=NumericRange(3, 37),  # Represents [3, 36] inclusive
                enabled=True,
            ),
            BasePaymentMethod(
                type="LOAN",
                loan_type="INSTALLMENT",
                loan_period_range=NumericRange(3, 4),  # Represents a 3-month term
                enabled=True,
            ),
            BasePaymentMethod(
                type="LOAN",
                loan_type="INSTALLMENT",
                loan_period_range=NumericRange(6, 7),  # Represents a 6-month term
                enabled=True,
            ),
            BasePaymentMethod(
                type="LOAN",
                loan_type="INSTALLMENT",
                loan_period_range=NumericRange(12, 13),  # Represents a 12-month term
                enabled=True,
            ),
            BasePaymentMethod(
                type="LOAN",
                loan_type="INSTALLMENT",
                loan_period_range=NumericRange(24, 25),  # Represents a 24-month term
                enabled=True,
            ),
        ]

        db.add_all(payment_methods_to_add)
        db.commit()
        click.echo("BasePaymentMethod table populated successfully!")

    except Exception as e:
        db.rollback()
        click.echo(f"An error occurred: {e}")
    finally:
        db.close()


@cli.command()
@click.argument("user_id")
@click.option(
    "--expiry-days",
    type=int,
    default=7,
    help="Session and refresh token expiry in days.",
)
@click.option(
    "--access-minutes",
    type=int,
    default=None,
    help="Access token expiry in minutes. Defaults to system setting.",
)
@click.option(
    "--validation-type",
    type=click.Choice(["ip", "user_agent", "all", "none"]),
    default="none",
    help="Validation type for the session (ip, user_agent, all, none).",
)
@click.option(
    "--ip-address", default="127.0.0.1", help="IP address for session validation."
)
@click.option(
    "--user-agent", default="Airshop CLI", help="User agent for session validation."
)
def create_user_session(
    user_id, expiry_days, access_minutes, validation_type, ip_address, user_agent
):
    """Creates a new user session and generates access/refresh tokens."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            click.echo(f"User with ID '{user_id}' not found.")
            return

        user_session_data = {
            "ip_address": ip_address,
            "user_agent": user_agent,
            "validation_type": validation_type,
        }

        tokens = security.create_access_and_refresh_tokens(
            db=db,
            user_id=user.id,
            user_session_data=user_session_data,
            refresh_token_expire_days=expiry_days,
            access_token_expire_minutes=access_minutes,
        )

        click.echo("User session created successfully!")
        click.echo(f"Access Token: {tokens['access_token']}")
        click.echo(f"Refresh Token: {tokens['refresh_token']}")

    except Exception as e:
        db.rollback()
        click.echo(f"An error occurred: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    cli()
