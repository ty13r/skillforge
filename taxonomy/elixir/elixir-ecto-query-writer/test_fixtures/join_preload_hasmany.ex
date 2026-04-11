# fixture: join-preload on has_many — 10x memory bloat anti-pattern
defmodule MyApp.Blog.Feed do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  @doc """
  Loads all active users with all their posts. Currently uses join-preload
  which materializes a Cartesian product in memory. At scale (10k users × 50
  posts each) this takes ~10x the memory of a separate-query preload.
  """
  def users_with_posts do
    from(u in User,
      join: p in assoc(u, :posts),
      where: u.active == true,
      preload: [posts: p]
    )
    |> Repo.all()
  end
end
