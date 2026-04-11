# fixture: context module with queries inline — should be extracted to UserQueries
defmodule MyApp.Accounts do
  @moduledoc """
  Accounts context. Contains business logic + all query functions. At 400+
  lines this file grows unboundedly. Query functions should live in a
  dedicated `MyApp.Accounts.UserQueries` module so the context only
  orchestrates; queries are the composition primitives.
  """
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  def list_active_users do
    from(u in User, where: u.active == true, order_by: [asc: u.name])
    |> Repo.all()
  end

  def list_admins do
    from(u in User, where: u.role == "admin", order_by: [asc: u.name])
    |> Repo.all()
  end

  def list_users_in_team(team_id) do
    from(u in User,
      where: u.team_id == ^team_id,
      where: u.active == true,
      order_by: [asc: u.name]
    )
    |> Repo.all()
  end

  def verified_users do
    from(u in User,
      where: not is_nil(u.email_verified_at),
      order_by: [desc: u.email_verified_at]
    )
    |> Repo.all()
  end
end
