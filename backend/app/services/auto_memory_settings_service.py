from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.models.user import (
    User,
)


class AutoMemorySettingsService:
    async def get_settings(
        self,
        *,
        user: User,
    ) -> bool:
        return bool(
            user.auto_memory_enabled
        )

    async def update_settings(
        self,
        *,
        db: AsyncSession,
        user: User,
        auto_memory_enabled: bool,
    ) -> bool:
        user.auto_memory_enabled = (
            auto_memory_enabled
        )

        await db.commit()

        await db.refresh(
            user
        )

        return bool(
            user.auto_memory_enabled
        )


auto_memory_settings_service = (
    AutoMemorySettingsService()
)