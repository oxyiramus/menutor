# Frontend behavioral audit tests

Run from repository root after installing the existing frontend dependencies:

```sh
node tests/frontend/run.mjs
```

The runner links `tests/frontend/node_modules` to the existing `frontend/node_modules` (ignored by Git). The dedicated Vite config uses a temporary cache and requires no changes to application files. It also runs the 16 existing composable tests. An individual file can be supplied as an argument.

This is the TDD test phase. Failures representing missing behavior are intentionally retained; do not weaken assertions or change the application during this phase.

## Audit coverage

All 12 rows in “Существенные пробелы фронтенда” are represented:

| Audit row | Tests and observable contract |
| --- | --- |
| Authentication/session/routes | `auth.test.ts`: login, restored session/new Pinia, logout, expired access refresh, revoked session blocked by actual router |
| Concurrent 401 | `refresh.test.ts`: actual Axios interceptors with transport adapter; one refresh, both retries, both promises settle on refusal, repeated 401 terminates |
| CRUD success/refusal/delete | `stores.test.ts`: actual product/recipe stores + useCrudView, resulting saved records, retained form/selection on failure, cancel sends no delete, single/batch failures announce no success; `recipe-form.test.ts` retains typed input on failure |
| Recipe editor | `recipe-form.test.ts`: mounted form and real ingredient picker/step editor, products + subrecipes, portions/pieces validation, store persistence/reopen with unchanged ingredient/step data |
| Menu planner/clipboard | `planner-preferences.test.ts`: add/move/reorder/remove request boundaries and participant identity, errors keep menu; source and pasted arrays cannot mutate clipboard |
| Shopping lists | `stores.test.ts`: generate/edit quantity+price/save/reload, purchased-only stays clean, toggle preserves unsaved edits, failed save retains dirty state |
| Preferences | `planner-preferences.test.ts`: nested allergen, reactive member switching, slot visibility, BLOCKED/ALLOWED product and recipe category contracts |
| Pagination/races/pickers | `stores.test.ts`, both product and recipe stores: search+category reset, last-page deletion correction, late old response ignored, full allItems distinct from page |
| Cost/flattened preview | `cost.test.ts`: absent/zero/full/partial distinct output, current ingredient/pieces request, late response ignored, explicit flattened preview refresh |
| Meal summary | `summary.test.ts`: selected original slot indices (4/9/12), standalone products, excluded nested recipe, confirmation before filtered generation |
| Import/export | `files.test.ts`: real file selection, counts/warnings, extension/server errors, selected export IDs, downloads only after success, filename and object URL cleanup |
| Mobile UI | `mobile.test.ts`: day/meal controls and action forwarding, week selection/visibility, member apply/cancel isolation, merged slot edit/remove identity, shared confirm/cancel behavior |

## Test boundaries

Vue components run in happy-dom, not a full browser. Tests protect component actions and data flow, not CSS breakpoints, layout, real touch/drag behavior or visual accessibility. Backend endpoints are mocked at the network boundary; store/composable logic under test is real. Mobile action-forwarding tests isolate GridCell; additional mobile add-control tests mount the actual GridCell. Recipe tests mount the actual picker and step editor. Summary tests stub presentation cards and trigger their documented public events; they exercise the real view selection/generation logic. Axios refresh tests execute real interceptors and mock only transport and the refresh endpoint.

Backend/browser end-to-end testing is not claimed. A rejected refresh intentionally leaves a request pending in the current implementation: the test uses a bounded settlement assertion rather than waiting indefinitely.
