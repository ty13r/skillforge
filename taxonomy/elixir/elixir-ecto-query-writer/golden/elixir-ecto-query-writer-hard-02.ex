defmodule MyApp.Blog.Rankings do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @doc """
  Returns each post with its position within its category, newest first.
  Uses Ecto's typed `row_number/0 |> over/1` form. Composable and
  type-checked — no raw SQL, no positional placeholders.
  """
  def posts_ranked_per_category do
    from(p in Post,
      select: %{
        id: p.id,
        title: p.title,
        category_id: p.category_id,
        rank: row_number() |> over(partition_by: p.category_id, order_by: [desc: p.inserted_at])
      }
    )
    |> Repo.all()
  end
end
