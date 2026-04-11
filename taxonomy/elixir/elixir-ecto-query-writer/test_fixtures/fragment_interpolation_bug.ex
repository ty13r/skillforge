# fixture: SQL injection via fragment interpolation — Ecto compiler rejects, Claude still writes
defmodule MyApp.Blog.Search do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Blog.Post

  @doc """
  Full-text search for posts. Currently string-interpolates user input
  directly into the fragment literal — SQL injection vector. Ecto's compiler
  actually rejects `#{}` inside fragment literals for this reason.
  """
  def find(user_input) do
    from(p in Post,
      where: fragment("p.body ILIKE '%#{user_input}%'")
    )
    |> Repo.all()
  end

  def by_score_threshold(threshold) do
    from(p in Post,
      where: fragment("p.score > #{threshold}")
    )
    |> Repo.all()
  end
end
