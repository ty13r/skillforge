defmodule MyApp.TextProcessor do
  def normalize(input) do
    input
    |> String.trim()
    |> String.downcase()
    |> String.replace(~r/[^a-z0-9 ]/, "")
    |> String.replace(~r/\s+/, " ")
    |> String.trim()
  end

  def slugify(title) do
    title
    |> String.trim()
    |> String.downcase()
    |> String.replace(" ", "-")
    |> String.replace(~r/[^a-z0-9-]/, "")
  end

  def summary(text) do
    text
    |> String.split(" ")
    |> Enum.take(10)
    |> Enum.join(" ")
    |> Kernel.<>("...")
  end
end
