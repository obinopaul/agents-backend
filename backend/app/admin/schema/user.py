from datetime import datetime
from typing import Annotated, Any

from pydantic import ConfigDict, Field, HttpUrl, PlainSerializer, model_validator
from typing_extensions import Self

from backend.app.admin.schema.dept import GetDeptDetail
from backend.app.admin.schema.role import GetRoleWithRelationDetail
from backend.common.enums import StatusType
from backend.common.schema import CustomEmailStr, CustomPhoneNumber, SchemaBase, ser_string


class AuthSchemaBase(SchemaBase):
    """用户认证基础模型"""

    username: str = Field(description='用户名')
    password: str = Field(description='密码')


class AuthLoginParam(AuthSchemaBase):
    """用户登录参数"""

    uuid: str | None = Field(None, description='验证码 UUID')
    captcha: str | None = Field(None, description='验证码')


class AddUserParam(AuthSchemaBase):
    """添加用户参数"""

    nickname: str | None = Field(None, description='昵称')
    email: CustomEmailStr | None = Field(None, description='邮箱')
    phone: CustomPhoneNumber | None = Field(None, description='手机号码')
    dept_id: int = Field(description='部门 ID')
    roles: list[int] = Field(description='角色 ID 列表')


class AddUserRoleParam(SchemaBase):
    """添加用户角色"""

    user_id: int = Field(description='用户 ID')
    role_id: int = Field(description='角色 ID')


class AddOAuth2UserParam(AuthSchemaBase):
    """添加 OAuth2 用户参数"""

    password: str | None = Field(None, description='密码')
    nickname: str | None = Field(None, description='昵称')
    email: CustomEmailStr | None = Field(None, description='邮箱')
    avatar: Annotated[HttpUrl, PlainSerializer(ser_string)] | None = Field(None, description='头像地址')


class RegisterUserParam(SchemaBase):
    """Public user registration parameters"""

    email: CustomEmailStr = Field(description='Email address (used for login)')
    password: str = Field(min_length=6, max_length=128, description='Password (min 6 characters)')
    name: str = Field(min_length=1, max_length=64, description='Display name')
    confirm_password: str | None = Field(None, description='Confirm password (optional)')

    @model_validator(mode='after')
    def validate_passwords(self) -> Self:
        """Validate that passwords match if confirm_password is provided"""
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError('Passwords do not match')
        return self


class RegisterUserResponse(SchemaBase):
    """Registration response with access token"""

    access_token: str = Field(description='JWT access token')
    token_type: str = Field(default='Bearer', description='Token type')
    expires_in: int = Field(description='Token expiry in seconds')
    user_id: int = Field(description='Created user ID')
    username: str = Field(description='Username (derived from email)')


class ResetPasswordParam(SchemaBase):
    """重置密码参数"""

    old_password: str = Field(description='旧密码')
    new_password: str = Field(description='新密码')
    confirm_password: str = Field(description='确认密码')


class UserInfoSchemaBase(SchemaBase):
    """用户信息基础模型"""

    dept_id: int | None = Field(None, description='部门 ID')
    username: str = Field(description='用户名')
    nickname: str = Field(description='昵称')
    avatar: Annotated[HttpUrl, PlainSerializer(ser_string)] | None = Field(None, description='头像地址')
    email: CustomEmailStr | None = Field(None, description='邮箱')
    phone: CustomPhoneNumber | None = Field(None, description='手机号')


class UpdateUserParam(UserInfoSchemaBase):
    """更新用户参数"""

    roles: list[int] = Field(description='角色 ID 列表')


class GetUserInfoDetail(UserInfoSchemaBase):
    """用户信息详情"""

    model_config = ConfigDict(from_attributes=True)

    dept_id: int | None = Field(None, description='部门 ID')
    id: int = Field(description='用户 ID')
    uuid: str = Field(description='用户 UUID')
    first_name: str = Field(default='', description='First name (derived from nickname)')
    last_name: str = Field(default='', description='Last name (derived from nickname)')
    status: StatusType = Field(description='状态')
    is_superuser: bool = Field(description='是否超级管理员')
    is_staff: bool = Field(description='是否管理员')
    is_multi_login: bool = Field(description='是否允许多端登录')
    join_time: datetime = Field(description='加入时间')
    last_login_time: datetime | None = Field(None, description='最后登录时间')

    @model_validator(mode='after')
    def derive_first_last_name(self) -> Self:
        """Derive first_name and last_name from the nickname field.

        Handles various name formats:
        - Single word: first_name = word, last_name = ''
        - Two words: first_name = first, last_name = second
        - Multiple words: first_name = first, last_name = rest joined
        - Empty/None: both default to ''
        """
        if self.nickname:
            parts = self.nickname.strip().split(None, 1)
            self.first_name = parts[0] if parts else ''
            self.last_name = parts[1] if len(parts) > 1 else ''
        return self


class GetUserInfoWithRelationDetail(GetUserInfoDetail):
    """用户信息关联详情"""

    model_config = ConfigDict(from_attributes=True)

    dept: GetDeptDetail | None = Field(None, description='部门信息')
    roles: list[GetRoleWithRelationDetail] = Field(description='角色列表')


class GetCurrentUserInfoWithRelationDetail(GetUserInfoWithRelationDetail):
    """当前用户信息关联详情"""

    model_config = ConfigDict(from_attributes=True)

    dept: str | None = Field(None, description='部门名称')
    roles: list[str] = Field(description='角色名称列表')

    @model_validator(mode='before')
    @classmethod
    def handel(cls, data: Any) -> Self:
        """处理部门和角色数据"""
        dept = data['dept']
        if dept:
            data['dept'] = dept['name']
        roles = data['roles']
        if roles:
            data['roles'] = [role['name'] for role in roles]
        return data
