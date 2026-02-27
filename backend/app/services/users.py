"""User service for CRUD operations."""

import uuid
from typing import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import Role, User
from app.schemas.user import UserCreate, UserFilter, UserUpdate


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID | None = None) -> None:
        """Initialize with database session and optional tenant filter."""
        self.db = db
        self.tenant_id = tenant_id

    async def get_by_id(self, user_id: str | uuid.UUID) -> User | None:
        """Get user by ID.

        Args:
            user_id: User's UUID.

        Returns:
            User if found, None otherwise.
        """
        query = select(User).where(User.id == user_id)
        if self.tenant_id is not None:
            query = query.where(User.tenant_id == self.tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: User's username.

        Returns:
            User if found, None otherwise.
        """
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: User's email.

        Returns:
            User if found, None otherwise.
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        filters: UserFilter | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[User], int]:
        """List users with optional filters and pagination.

        Args:
            filters: Optional filters (role, is_active, search).
            page: Page number (1-indexed).
            page_size: Number of results per page.

        Returns:
            Tuple of (users list, total count).
        """
        query = select(User)

        # Apply tenant filter
        if self.tenant_id is not None:
            query = query.where(User.tenant_id == self.tenant_id)

        # Apply filters
        if filters:
            if filters.role:
                query = query.where(User.role == filters.role)
            if filters.is_active is not None:
                query = query.where(User.is_active == filters.is_active)
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        User.username.ilike(search_term),
                        User.email.ilike(search_term),
                    )
                )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())

        # Execute query
        result = await self.db.execute(query)
        users = result.scalars().all()

        return users, total

    async def create(self, data: UserCreate) -> User:
        """Create a new user.

        Args:
            data: User creation data.

        Returns:
            Created user.

        Raises:
            ValueError: If username or email already exists.
        """
        # Check for existing username
        if await self.get_by_username(data.username):
            raise ValueError(f"Username '{data.username}' already exists")

        # Check for existing email
        if await self.get_by_email(data.email):
            raise ValueError(f"Email '{data.email}' already exists")

        # Create user
        user = User(
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
            is_active=True,
            tenant_id=self.tenant_id,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update(self, user: User, data: UserUpdate) -> User:
        """Update an existing user.

        Args:
            user: User to update.
            data: Update data.

        Returns:
            Updated user.

        Raises:
            ValueError: If username or email conflicts.
        """
        # Check username uniqueness if changing
        if data.username and data.username != user.username:
            if await self.get_by_username(data.username):
                raise ValueError(f"Username '{data.username}' already exists")
            user.username = data.username

        # Check email uniqueness if changing
        if data.email and data.email != user.email:
            if await self.get_by_email(data.email):
                raise ValueError(f"Email '{data.email}' already exists")
            user.email = data.email

        # Update other fields
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update_password(self, user: User, new_password: str) -> User:
        """Update user's password.

        Args:
            user: User to update.
            new_password: New password (plain text).

        Returns:
            Updated user.
        """
        user.password_hash = hash_password(new_password)
        await self.db.flush()
        return user

    async def deactivate(self, user: User) -> User:
        """Deactivate a user (soft delete).

        Args:
            user: User to deactivate.

        Returns:
            Deactivated user.
        """
        user.is_active = False
        await self.db.flush()
        return user

    async def activate(self, user: User) -> User:
        """Reactivate a user.

        Args:
            user: User to activate.

        Returns:
            Activated user.
        """
        user.is_active = True
        await self.db.flush()
        return user

    async def count_by_role(self) -> dict[str, int]:
        """Get user count by role.

        Returns:
            Dictionary with role counts.
        """
        result = await self.db.execute(
            select(User.role, func.count(User.id))
            .group_by(User.role)
        )
        counts = {role.value: 0 for role in Role}
        for role, count in result.all():
            counts[role.value] = count
        return counts
