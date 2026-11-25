"""ApplicationContainer — slim orchestrator calling domain sub-registries."""

from sqlalchemy.orm import Session

from backend.application.use_cases.assign_preferences import AssignPreferencesToMember
from backend.application.use_cases.auth import (
    ChangePassword,
    GetCurrentUser,
    LoginUser,
    LogoutUser,
    RefreshAccessToken,
    RegisterUser,
    UpdateProfile,
)
from backend.application.use_cases.calculate_recipe_cost import CalculateRecipeCost
from backend.application.use_cases.crud_base import GetEntity, ListEntities
from backend.application.use_cases.export_entities import ExportEntities
from backend.application.use_cases.export_shopping_list import ExportShoppingList
from backend.application.use_cases.flatten_recipe_products import FlattenRecipeProducts
from backend.application.use_cases.generate_and_save_shopping_list import (
    GenerateAndSaveShoppingList,
)
from backend.application.use_cases.generate_filtered_shopping_list import (
    GenerateFilteredShoppingList,
)
from backend.application.use_cases.generate_meal_summary import GenerateMealSummary
from backend.application.use_cases.generate_shopping_list import GenerateShoppingList
from backend.application.use_cases.import_entities import ImportEntities
from backend.application.use_cases.manage_category import CategoryBundle
from backend.application.use_cases.manage_family import (
    CreateFamilyMember,
    DeleteFamilyMember,
    EditFamilyMember,
    ListFamilyMembers,
)
from backend.application.use_cases.manage_meal_type import (
    CheckMealTypeUsage,
    CreateMealType,
    DeleteMealType,
    ListMealTypes,
    UpdateMealType,
)
from backend.application.use_cases.manage_preference import (
    CreatePreference,
    DeletePreference,
    UpdatePreference,
)
from backend.application.use_cases.manage_product import (
    CreateProduct,
    DeleteProduct,
    EditProduct,
    ListProductCategories,
    ListProducts,
    UpdateProductPrice,
)
from backend.application.use_cases.manage_recipe import (
    CreateRecipe,
    DeleteRecipeWithDependents,
    EditRecipe,
    GetRecipe,
    ListRecipeCategories,
    ListRecipes,
)
from backend.application.use_cases.manage_saved_shopping_list import (
    CopySavedShoppingList,
    CreateSavedShoppingList,
    DeleteSavedShoppingList,
    GetSavedShoppingList,
    ListSavedShoppingLists,
    RenameSavedShoppingList,
    ToggleItemPurchased,
    UpdateSavedShoppingList,
)
from backend.application.use_cases.match_recipe_preferences import (
    MatchRecipePreferences,
)
from backend.application.use_cases.plan_menu import (
    AddDishToSlot,
    ClearMenu,
    CopyMenu,
    CreateMenu,
    DeleteMenu,
    ListMenus,
    LoadMenu,
    MoveSlotInMenu,
    RemoveItemFromSlot,
    SaveMenu,
)
from backend.application.use_cases.preview_flattened_products import (
    PreviewFlattenedProducts,
)
from backend.application.use_cases.preview_recipe_cost import PreviewRecipeCost
from backend.application.use_cases.validate_sub_recipe import ValidateSubRecipe
from backend.composition._auth import _wire_auth
from backend.composition._categories import _wire_categories
from backend.composition._family import _wire_family
from backend.composition._import_export import _wire_import_export
from backend.composition._infrastructure import _create_infrastructure
from backend.composition._meal_types import _wire_meal_types
from backend.composition._menus import _wire_menus
from backend.composition._preferences import _wire_preferences
from backend.composition._products import _wire_products
from backend.composition._recipes import _wire_recipes
from backend.composition._shopping import _wire_shopping


class ApplicationContainer:
    """Dependency graph bound to one HTTP request."""

    add_dish_to_slot: AddDishToSlot
    assign_preferences_to_member: AssignPreferencesToMember
    calculate_recipe_cost: CalculateRecipeCost
    change_password: ChangePassword
    check_meal_type_usage: CheckMealTypeUsage
    clear_menu: ClearMenu
    copy_menu: CopyMenu
    copy_saved_shopping_list: CopySavedShoppingList
    create_family_member: CreateFamilyMember
    create_meal_type: CreateMealType
    create_menu: CreateMenu
    create_preference: CreatePreference
    create_product: CreateProduct
    create_recipe: CreateRecipe
    create_saved_shopping_list: CreateSavedShoppingList
    delete_family_member: DeleteFamilyMember
    delete_meal_type: DeleteMealType
    delete_menu: DeleteMenu
    delete_preference: DeletePreference
    delete_product: DeleteProduct
    delete_recipe: DeleteRecipeWithDependents
    delete_saved_shopping_list: DeleteSavedShoppingList
    edit_family_member: EditFamilyMember
    edit_product: EditProduct
    edit_recipe: EditRecipe
    export_entities: ExportEntities
    export_shopping_list: ExportShoppingList
    flatten_recipe_products: FlattenRecipeProducts
    generate_and_save_shopping_list: GenerateAndSaveShoppingList
    generate_filtered_shopping_list: GenerateFilteredShoppingList
    generate_meal_summary: GenerateMealSummary
    generate_shopping_list: GenerateShoppingList
    get_current_user: GetCurrentUser
    get_preference: GetEntity
    get_recipe: GetRecipe
    get_saved_shopping_list: GetSavedShoppingList
    import_entities: ImportEntities
    list_family_members: ListFamilyMembers
    list_meal_types: ListMealTypes
    list_menus: ListMenus
    list_preferences: ListEntities
    list_product_categories: ListProductCategories
    list_products: ListProducts
    list_recipe_categories: ListRecipeCategories
    list_recipes: ListRecipes
    list_saved_shopping_lists: ListSavedShoppingLists
    load_menu: LoadMenu
    login_user: LoginUser
    logout_user: LogoutUser
    match_recipe_preferences: MatchRecipePreferences
    move_slot_in_menu: MoveSlotInMenu
    preview_flattened_products: PreviewFlattenedProducts
    preview_recipe_cost: PreviewRecipeCost
    product_categories: CategoryBundle
    recipe_categories: CategoryBundle
    refresh_access_token: RefreshAccessToken
    register_user: RegisterUser
    remove_item_from_slot: RemoveItemFromSlot
    rename_saved_shopping_list: RenameSavedShoppingList
    save_menu: SaveMenu
    toggle_item_purchased: ToggleItemPurchased
    update_meal_type: UpdateMealType
    update_preference: UpdatePreference
    update_product_price: UpdateProductPrice
    update_profile: UpdateProfile
    update_saved_shopping_list: UpdateSavedShoppingList
    validate_sub_recipe: ValidateSubRecipe

    def __init__(self, session: Session, jwt_secret: str) -> None:
        infra = _create_infrastructure(session, jwt_secret)

        for name, obj in _wire_auth(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_recipes(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_products(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_menus(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_categories(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_family(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_shopping(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_preferences(infra).items():
            setattr(self, name, obj)
        for name, obj in _wire_meal_types(infra).items():
            setattr(self, name, obj)

        # import/export wiring needs generate_shopping_list already set
        for name, obj in _wire_import_export(
            infra, self.generate_shopping_list
        ).items():
            setattr(self, name, obj)
