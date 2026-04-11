# fixture: window function expressed as raw fragment — has typed equivalent
defmodule MyApp.Blog.Rankings do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @doc """
  Returns each post with its position within its category, newest first.
  Currently expressed as a raw `fragment/1` with a positional OVER clause.
  Ecto provides a typed `row_number() |> over(partition_by: ..., order_by: ...)`
  form that produces the same SQL but is composable and type-checked.
  """
  def posts_ranked_per_category do
    from(p in Post,
      select: %{
        id: p.id,
        title: p.title,
        category_id: p.category_id,
        rank:
          fragment(
            "row_number() OVER (PARTITION BY ? ORDER BY ? DESC)",
            p.category_id,
            p.inserted_at
          )
      }
    )
    |> Repo.all()
  end
end
