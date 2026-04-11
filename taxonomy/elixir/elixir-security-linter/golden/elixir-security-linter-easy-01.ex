# golden: atom-exhaustion fix — replace String.to_atom with allowlisted map
defmodule MyAppWeb.PostController do
  use MyAppWeb, :controller

  alias MyApp.Blog
  alias MyApp.Blog.Post

  @sort_fields %{
    "inserted_at" => :inserted_at,
    "title" => :title,
    "published_at" => :published_at
  }

  @directions %{"asc" => :asc, "desc" => :desc}

  def index(conn, params) do
    sort_by = Map.get(@sort_fields, params["sort_by"], :inserted_at)
    direction = Map.get(@directions, params["dir"], :desc)

    posts =
      Post
      |> MyApp.Repo.all(order_by: [{direction, sort_by}])

    render(conn, :index, posts: posts)
  end

  def show(conn, %{"id" => id, "view" => view}) do
    template =
      case view do
        "summary" -> :show_summary
        "full" -> :show_full
        _ -> :show
      end

    post = Blog.get_post!(id)
    render(conn, template, post: post)
  end
end
