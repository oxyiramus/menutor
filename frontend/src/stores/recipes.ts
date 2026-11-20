import { accountSessionSignal } from '@/api/accountSession'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { ActiveCategory, Recipe, RecipeCreate } from '@/api/types'
import {
  batchDeleteRecipes,
  createRecipe,
  deleteRecipe,
  fetchRecipeCategories,
  fetchRecipes,
  updateRecipe,
} from '@/api/client'
import { PAGE_SIZE } from '@/utils/pagination'
import { useToastStore } from './toast'

export const useRecipeStore = defineStore('recipes', () => {
  const items = ref<Recipe[]>([])
  const allItems = ref<Recipe[]>([])
  const categories = ref<ActiveCategory[]>([])
  const loading = ref(false)
  const page = ref(1)
  const total = ref(0)
  const pageSize = ref(PAGE_SIZE)
  const search = ref('')
  const categoryId = ref<number | null>(null)

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  let pageRequest = 0

  async function _loadPage(): Promise<void> {
    const request = ++pageRequest
    const data = await fetchRecipes({
      page: page.value,
      search: search.value || undefined,
      categoryId: categoryId.value ?? undefined,
    })
    if (request !== pageRequest) return
    const lastPage = Math.max(1, Math.ceil(data.total / (data.page_size || PAGE_SIZE)))
    if (page.value > lastPage) {
      page.value = lastPage
      await _loadPage()
      return
    }
    items.value = data.items
    total.value = data.total
    pageSize.value = data.page_size || PAGE_SIZE
  }

  async function _loadAll() {
    const data = await fetchRecipes()
    allItems.value = data.items
  }

  async function load() {
    const session = accountSessionSignal()
    loading.value = true
    try {
      const [, cats] = await Promise.all([
        Promise.all([_loadPage(), _loadAll()]),
        fetchRecipeCategories(),
      ])
      categories.value = cats
    } catch {
      if (!session.aborted) useToastStore().show('Ошибка загрузки рецептов', 'error')
    } finally {
      if (!session.aborted) loading.value = false
    }
  }

  async function setPage(p: number) {
    const session = accountSessionSignal()
    page.value = p
    loading.value = true
    try {
      await _loadPage()
    } catch {
      if (!session.aborted) useToastStore().show('Ошибка загрузки рецептов', 'error')
    } finally {
      if (!session.aborted) loading.value = false
    }
  }

  async function setFilters(newSearch: string, newCategoryId: number | null) {
    const session = accountSessionSignal()
    search.value = newSearch
    categoryId.value = newCategoryId
    page.value = 1
    loading.value = true
    try {
      await _loadPage()
    } catch {
      if (!session.aborted) useToastStore().show('Ошибка загрузки рецептов', 'error')
    } finally {
      if (!session.aborted) loading.value = false
    }
  }

  async function create(data: RecipeCreate): Promise<Recipe> {
    const item = await createRecipe(data)
    await Promise.all([_loadPage(), _loadAll()])
    useToastStore().show('Рецепт создан', 'success')
    return item
  }

  async function update(id: number, data: RecipeCreate): Promise<Recipe> {
    const item = await updateRecipe(id, data)
    await Promise.all([_loadPage(), _loadAll()])
    useToastStore().show('Рецепт обновлён', 'success')
    return item
  }

  async function remove(id: number) {
    await deleteRecipe(id)
    await Promise.all([_loadPage(), _loadAll()])
    useToastStore().show('Рецепт удалён', 'success')
  }

  async function removeMany(ids: number[]) {
    if (!ids.length) return
    await batchDeleteRecipes(ids)
    await Promise.all([_loadPage(), _loadAll()])
    useToastStore().show('Рецепты удалены', 'success')
  }

  async function removeAll() {
    const ids = allItems.value.map((i) => i.id)
    if (!ids.length) return
    await batchDeleteRecipes(ids)
    await Promise.all([_loadPage(), _loadAll()])
    useToastStore().show('Рецепты удалены', 'success')
  }

  function reset() {
    items.value = []
    allItems.value = []
    categories.value = []
    loading.value = false
    page.value = 1
    total.value = 0
    pageSize.value = PAGE_SIZE
    search.value = ''
    categoryId.value = null
  }

  return {
    reset,
    items,
    allItems,
    categories,
    loading,
    page,
    total,
    totalPages,
    search,
    categoryId,
    pageSize,
    load,
    setPage,
    setFilters,
    create,
    update,
    remove,
    removeMany,
    removeAll,
  }
})
