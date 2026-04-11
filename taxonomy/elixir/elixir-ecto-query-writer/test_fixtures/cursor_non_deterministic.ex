# fixture: cursor pagination without unique tie-breaker — drops/duplicates rows
defmodule MyApp.Blog.FeedCursor do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @page_size 20

  @doc """
  Cursor-paginates posts ordered by `published_at`. BUG: `published_at` is not
  unique — several posts can share the same second. When the cursor value
  matches multiple rows, the WHERE clause drops/duplicates those rows across
  pages. Needs a secondary unique column (`id`) for a deterministic sort.
  """
  def feed(cursor \\ nil) do
    base =
      from(p in Post,
        where: p.published == true,
        order_by: [desc: p.published_at],
        limit: ^@page_size
      )

    case cursor do
      nil -> Repo.all(base)
      ts -> Repo.all(from p in base, where: p.published_at < ^ts)
    end
  end
end
