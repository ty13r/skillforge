defmodule MyApp.Blog.Feed do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Loads all active users with all their posts using a separate-query preload.
  Ecto issues one query per association level (two round trips total) but
  the per-user memory cost is O(1) — no Cartesian product materialized.
  """
  def users_with_posts do
    from(u in User,
      where: u.active == true,
      preload: [:posts]
    )
    |> Repo.all()
  end
end
