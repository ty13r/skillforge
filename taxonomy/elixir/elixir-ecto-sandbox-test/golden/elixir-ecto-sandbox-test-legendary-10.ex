# Golden: LiveView assign_async test that correctly awaits async with render_async/1 + allow/3 where needed
defmodule MyAppWeb.UserListLiveTest do
  use MyAppWeb.ConnCase, async: true

  import Phoenix.LiveViewTest

  alias MyApp.Accounts

  test "lists users loaded via assign_async", %{conn: conn} do
    {:ok, _user} = Accounts.create_user(%{email: "a@example.com"})
    {:ok, _user2} = Accounts.create_user(%{email: "b@example.com"})

    {:ok, lv, html} = live(conn, ~p"/users")

    # Before render_async/1 the async assign is still in its loading state.
    assert html =~ "Loading users..."

    # render_async/1 awaits every pending assign_async and re-renders.
    # Without this call the assertion on user rows would silently pass/fail
    # depending on timing — NOT a sandbox bug, but a test synchronization bug.
    html = render_async(lv)

    assert html =~ "a@example.com"
    assert html =~ "b@example.com"
    refute html =~ "Loading users..."
  end
end
