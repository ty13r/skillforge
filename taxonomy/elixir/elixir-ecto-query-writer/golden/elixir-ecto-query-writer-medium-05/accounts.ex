# golden: slim context delegating to UserQueries
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
