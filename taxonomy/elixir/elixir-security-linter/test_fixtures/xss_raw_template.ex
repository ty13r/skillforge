# fixture: HEEx template + controller using raw/1 on user-controlled content
# Vulnerability: XSS via raw/1 bypass of HEEx auto-escaping, and a controller
# that sends_resp with interpolated HTML.
defmodule MyAppWeb.PostHTML do
  use MyAppWeb, :html

  def show(assigns) do
    ~H"""
    <article>
      <h1>{@post.title}</h1>
      <div class="body">
        {raw(@post.body_html)}
      </div>
      <footer>Posted by {raw(@post.author_name)}</footer>
    </article>
    """
  end
end

defmodule MyAppWeb.GreetingController do
  use MyAppWeb, :controller

  def hello(conn, %{"name" => name}) do
    html(conn, "<h1>Welcome back, #{name}!</h1>")
  end

  def download(conn, %{"content_type" => ct, "body" => body}) do
    conn
    |> put_resp_content_type(ct)
    |> send_resp(200, body)
  end
end
