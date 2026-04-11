# golden: CSP nonce integration for LiveView — remove unsafe-inline
defmodule MyAppWeb.Router do
  use MyAppWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :assign_csp_nonce
    plug :put_root_layout, html: {MyAppWeb.Layouts, :root}
    plug :put_secure_browser_headers, %{
      "content-security-policy" => ""
    }
    plug :put_dynamic_csp
  end

  defp assign_csp_nonce(conn, _) do
    nonce = 16 |> :crypto.strong_rand_bytes() |> Base.encode16(case: :lower)

    conn
    |> Plug.Conn.assign(:csp_nonce, nonce)
  end

  defp put_dynamic_csp(conn, _) do
    nonce = conn.assigns[:csp_nonce]

    csp =
      "default-src 'self'; " <>
        "script-src 'self' 'nonce-#{nonce}'; " <>
        "style-src 'self' 'nonce-#{nonce}'; " <>
        "object-src 'none'; base-uri 'self'"

    Plug.Conn.put_resp_header(conn, "content-security-policy", csp)
  end

  scope "/", MyAppWeb do
    pipe_through :browser
    live "/posts", PostLive.Index, :index
  end
end
