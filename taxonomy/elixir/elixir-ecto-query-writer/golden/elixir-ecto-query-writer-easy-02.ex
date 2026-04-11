defmodule MyApp.Accounts.ReportGenerator do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Builds a per-user summary report. Preloads `:posts` at query time so each
  user already has its posts materialized before iteration — one query for
  users, one query for posts, regardless of user count.
  """
  def generate do
    users =
      from(u in User, preload: [:posts])
      |> Repo.all()

    Enum.map(users, fn user ->
      %{
        name: user.name,
        post_count: length(user.posts)
      }
    end)
  end
end
