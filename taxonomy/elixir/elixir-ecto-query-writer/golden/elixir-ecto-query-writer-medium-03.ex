defmodule MyApp.Accounts.Sync do
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Bulk upsert that refreshes only the `name` field for existing users.
  `conflict_target: :email` tells PostgreSQL which unique index defines
  the conflict. `{:replace, [:name, :updated_at]}` only rewrites those
  specific columns — `email`, `age`, `last_login_at`, and every other
  field stay intact.
  """
  def sync_names(entries) do
    Repo.insert_all(
      User,
      entries,
      on_conflict: {:replace, [:name, :updated_at]},
      conflict_target: :email
    )
  end
end
