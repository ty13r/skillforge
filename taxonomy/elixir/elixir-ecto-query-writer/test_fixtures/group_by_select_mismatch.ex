# fixture: select references non-grouped fields — Ecto raises at compile time
defmodule MyApp.Blog.Stats do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @doc """
  Returns post counts per category along with the category name. BUG:
  `group_by` only includes `category_id`, but `select` references the
  un-grouped `name`. Ecto requires every selected field to either appear
  in `group_by` or be wrapped in an aggregate function.
  """
  def post_count_by_category do
    from(p in Post,
      join: c in assoc(p, :category),
      group_by: c.id,
      select: {c.id, c.name, count(p.id)}
    )
    |> Repo.all()
  end
end
