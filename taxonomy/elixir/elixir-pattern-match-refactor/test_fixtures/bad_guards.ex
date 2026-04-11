# fixture: Functions that should use guard clauses but use body if/else or illegal
# guard expressions instead. Also contains `when not is_nil(x)` — Credo.NegatedIsNil.
defmodule MyApp.Validator do
  def validate_age(age) do
    if is_integer(age) and age >= 0 and age <= 150 do
      :ok
    else
      {:error, :invalid_age}
    end
  end

  def validate_email(email) do
    if is_binary(email) and String.contains?(email, "@") do
      :ok
    else
      {:error, :invalid_email}
    end
  end

  def call_service(%{req: req}) when not is_nil(req) do
    do_call(req)
  end

  def call_service(_), do: {:error, :missing_req}

  def process(thing) when not is_nil(thing) do
    thing
  end

  def format_user(user) do
    if user != nil && is_binary(user.name) && byte_size(user.name) > 0 do
      String.upcase(user.name)
    else
      "UNKNOWN"
    end
  end

  defp do_call(req), do: {:ok, req}
end
