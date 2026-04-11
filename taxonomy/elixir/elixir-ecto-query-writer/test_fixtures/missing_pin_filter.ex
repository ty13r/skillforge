# fixture: query missing pin operator — silent bug risk, won't compile on some patterns
defmodule MyApp.Accounts do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  def get_by_email(email) do
    from(u in User, where: u.email == email)
    |> Repo.one()
  end

  def active_users_in_team(team_id) do
    from(u in User,
      where: u.team_id == team_id,
      where: u.active == true
    )
    |> Repo.all()
  end

  def list_by_role(role) do
    User
    |> where([u], u.role == role)
    |> Repo.all()
  end
end
