# fixture: offset/limit pagination — linear cost at high page numbers
defmodule MyApp.Blog.Feed do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @page_size 20

  @doc """
  Fetches a page of published posts ordered by recency. Uses OFFSET/LIMIT
  pagination. At page 1000, PostgreSQL must still scan and discard 20,000
  rows before returning 20 — linear degradation that cursor pagination avoids.
  """
  def feed(page) do
    offset = (page - 1) * @page_size

    from(p in Post,
      where: p.published == true,
      order_by: [desc: p.published_at],
      limit: ^@page_size,
      offset: ^offset
    )
    |> Repo.all()
  end
end
