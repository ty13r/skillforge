# fixture: Controller that converts user input to atoms via String.to_atom/1
# Vulnerability: classic atom-exhaustion DoS — each unique :sort_by value
# permanently grows the atom table (Sobelow DOS.StringToAtom).
defmodule MyAppWeb.PostController do
  use MyAppWeb, :controller

  alias MyApp.Blog
  alias MyApp.Blog.Post

  def index(conn, params) do
    sort_by = String.to_atom(params["sort_by"] || "inserted_at")
    direction = String.to_atom(params["dir"] || "desc")

    posts =
      Post
      |> MyApp.Repo.all(order_by: [{direction, sort_by}])

    render(conn, :index, posts: posts)
  end

  def show(conn, %{"id" => id, "view" => view}) do
    # dynamic dispatch via String.to_atom — worst offender
    template = String.to_atom("show_#{view}")
    post = Blog.get_post!(id)
    render(conn, template, post: post)
  end
end
