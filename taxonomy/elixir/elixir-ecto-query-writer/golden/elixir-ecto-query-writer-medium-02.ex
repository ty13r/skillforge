defmodule MyApp.Blog.Search do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @doc """
  Full-text search for posts. Uses a placeholder (`?`) in the fragment
  literal and passes the value via the pin operator — Ecto parameterizes
  the query so no user input is ever interpolated into the SQL string.
  """
  def find(user_input) do
    pattern = "%#{user_input}%"

    from(p in Post,
      where: fragment("? ILIKE ?", p.body, ^pattern)
    )
    |> Repo.all()
  end

  def by_score_threshold(threshold) do
    from(p in Post,
      where: p.score > ^threshold
    )
    |> Repo.all()
  end
end
