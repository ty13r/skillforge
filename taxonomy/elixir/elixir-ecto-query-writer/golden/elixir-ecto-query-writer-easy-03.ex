defmodule MyApp.Blog.Stats do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @doc """
  Returns post counts per category. Both `c.id` and `c.name` now appear
  in `group_by` so the select shape is valid.
  """
  def post_count_by_category do
    from(p in Post,
      join: c in assoc(p, :category),
      group_by: [c.id, c.name],
      select: {c.id, c.name, count(p.id)}
    )
    |> Repo.all()
  end
end
