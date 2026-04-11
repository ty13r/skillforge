defmodule MyApp.Blog.Feed do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @page_size 20

  @doc """
  Cursor-paginated feed. Deterministic ordering via `(published_at desc, id desc)`
  — `id` is the unique tie-breaker. The cursor is a tuple `{ts, id}` and the
  row-wise comparison `(published_at, id) < (^ts, ^id)` selects strictly older
  rows without dropping ties.
  """
  def feed(cursor \\ nil)

  def feed(nil) do
    from(p in Post,
      where: p.published == true,
      order_by: [desc: p.published_at, desc: p.id],
      limit: ^@page_size
    )
    |> Repo.all()
  end

  def feed({ts, last_id}) do
    from(p in Post,
      where: p.published == true,
      where:
        p.published_at < ^ts or
          (p.published_at == ^ts and p.id < ^last_id),
      order_by: [desc: p.published_at, desc: p.id],
      limit: ^@page_size
    )
    |> Repo.all()
  end
end
