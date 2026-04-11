# fixture: String parsing using String.starts_with? + String.slice and regex where binary
# pattern matching would be cleaner.
defmodule MyApp.CommandParser do
  def parse(line) do
    if String.starts_with?(line, "SET ") do
      rest = String.slice(line, 4, String.length(line))
      {:set, rest}
    else
      if String.starts_with?(line, "GET ") do
        rest = String.slice(line, 4, String.length(line))
        {:get, rest}
      else
        if String.starts_with?(line, "DEL ") do
          rest = String.slice(line, 4, String.length(line))
          {:del, rest}
        else
          case Regex.run(~r/^PING\s*(.*)$/, line) do
            [_, payload] -> {:ping, payload}
            nil -> {:error, :unknown}
          end
        end
      end
    end
  end

  def extract_prefix(input) do
    if String.starts_with?(input, "v1:") do
      rest = String.slice(input, 3, String.length(input))
      {:v1, rest}
    else
      if String.starts_with?(input, "v2:") do
        rest = String.slice(input, 3, String.length(input))
        {:v2, rest}
      else
        {:unknown, input}
      end
    end
  end
end
