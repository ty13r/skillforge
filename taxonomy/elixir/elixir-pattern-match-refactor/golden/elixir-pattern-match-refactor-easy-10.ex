defmodule MyApp.Validator do
  def validate_age(age) when is_integer(age) and age >= 0 and age <= 150, do: :ok
  def validate_age(_), do: {:error, :invalid_age}

  def validate_email(email) when is_binary(email) do
    if String.contains?(email, "@"), do: :ok, else: {:error, :invalid_email}
  end

  def validate_email(_), do: {:error, :invalid_email}
end
