# fixture: insert_all with :replace_all — writes NULLs for omitted fields
defmodule MyApp.Accounts.Sync do
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Periodic bulk upsert that refreshes a subset of user fields from an
  external source. Uses `on_conflict: :replace_all` — which silently
  overwrites `email`, `age`, and `last_login_at` with NULL for any row
  that only carries `name` in the incoming payload. The `conflict_target`
  is also missing, so PostgreSQL raises a cryptic SQL error.
  """
  def sync_names(entries) do
    Repo.insert_all(
      User,
      entries,
      on_conflict: :replace_all
    )
  end
end
