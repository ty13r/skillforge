# fixture: Test uses hard-coded email — collides across async tests via unique constraint
defmodule MyApp.AccountsTest do
  use MyApp.DataCase, async: true

  alias MyApp.Accounts

  describe "create_user/1" do
    test "creates a user with valid attrs" do
      # BUG: hard-coded email. Other tests in this module (or in a sibling module)
      # create users with the same email, and though each test rolls back, a
      # concurrent transaction in another async test can race the unique
      # constraint check. Unique_constraint/2 validation may pass for both
      # transactions before either commits, but only one INSERT wins.
      assert {:ok, user} = Accounts.create_user(%{email: "test@example.com"})
      assert user.email == "test@example.com"
    end

    test "creates a user with a different name" do
      assert {:ok, user} = Accounts.create_user(%{email: "test@example.com", name: "Jane"})
      assert user.name == "Jane"
    end
  end
end
