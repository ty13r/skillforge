# fixture: classic N+1 — iteration triggers one query per user
defmodule MyApp.Accounts.ReportGenerator do
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Builds a per-user summary report. The outer query returns all users; the
  inner call to `user.posts` triggers an N+1 because `posts` was never
  preloaded at query time. With 200 users this runs 201 queries.
  """
  def generate do
    users = Repo.all(User)

    Enum.map(users, fn user ->
      %{
        name: user.name,
        post_count: length(user.posts)
      }
    end)
  end
end
