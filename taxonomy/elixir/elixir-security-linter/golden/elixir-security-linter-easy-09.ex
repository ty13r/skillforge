# golden: raw/1 XSS fix — strip raw wrapper, rely on HEEx auto-escaping
defmodule MyAppWeb.PostHTML do
  use MyAppWeb, :html

  def show(assigns) do
    ~H"""
    <article>
      <h1>{@post.title}</h1>
      <div class="body">
        {@post.body_html}
      </div>
      <footer>Posted by {@post.author_name}</footer>
    </article>
    """
  end
end

defmodule MyAppWeb.GreetingController do
  use MyAppWeb, :controller

  def hello(conn, %{"name" => name}) do
    render(conn, :hello, name: name)
  end

  def download(conn, %{"body" => body}) do
    conn
    |> put_resp_content_type("text/plain")
    |> send_resp(200, body)
  end
end
