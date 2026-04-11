defmodule MyApp.Accounts.UserQueries do
  @moduledoc """
  Pure query-builder module. Every function takes and returns an
  `Ecto.Queryable` so they can be composed together, and defaults the
  base query to `from(u in User, as: :user)` so named-binding joins
  still resolve from outer functions.
  """
  import Ecto.Query
  alias MyApp.Accounts.User

  def base, do: from(u in User, as: :user)

  def active(query \\ base()) do
    from([user: u] in query, where: u.active == true)
  end

  def by_role(query \\ base(), role) do
    from([user: u] in query, where: u.role == ^role)
  end

  def in_team(query \\ base(), team_id) do
    from([user: u] in query, where: u.team_id == ^team_id)
  end

  def verified(query \\ base()) do
    from([user: u] in query, where: not is_nil(u.email_verified_at))
  end

  def by_name(query \\ base()) do
    from([user: u] in query, order_by: [asc: u.name])
  end
end

defmodule MyApp.Accounts do
  alias MyApp.Repo
  alias MyApp.Accounts.UserQueries, as: Q

  def list_active_users do
    Q.base() |> Q.active() |> Q.by_name() |> Repo.all()
  end

  def list_admins do
    Q.base() |> Q.by_role("admin") |> Q.by_name() |> Repo.all()
  end

  def list_users_in_team(team_id) do
    Q.base() |> Q.in_team(team_id) |> Q.active() |> Q.by_name() |> Repo.all()
  end

  def verified_users do
    Q.base() |> Q.verified() |> Repo.all()
  end
end
