import { Highlight, Prism, themes } from "prism-react-renderer";

// Register additional languages not in the default prism-react-renderer bundle.
// We define grammars inline so there's no dependency on prismjs components.

// Bash / Shell
Prism.languages.bash = {
  comment: { pattern: /(^|[^\\])#.*/, lookbehind: true },
  string: [
    { pattern: /\$'(?:[^'\\]|\\.)*'/, greedy: true },
    { pattern: /"(?:[^"\\$]|\\.|`[^`]*`|\$(?:\([^)]+\)|[^(]))*"/, greedy: true },
    { pattern: /'[^']*'/, greedy: true },
  ],
  variable: /\$(?:\w+|[!#?*@$]|\{[^}]+\})/,
  keyword:
    /\b(?:if|then|else|elif|fi|for|while|do|done|in|case|esac|function|return|local|export|readonly|declare|typeset|unset|set|shift|exit|exec|eval|source|true|false)\b/,
  builtin:
    /\b(?:echo|printf|read|cd|pwd|pushd|popd|test|grep|sed|awk|find|xargs|cat|head|tail|sort|uniq|wc|tr|cut|tee|mkdir|rm|cp|mv|ln|chmod|chown|curl|wget)\b/,
  operator: /&&|\|\||[!=<>]=?|<<|>>|[|&;]/,
  function: { pattern: /\b\w+(?=\s*\()/, greedy: true },
  number: /\b\d+\b/,
  punctuation: /[()[\]{};]/,
};
Prism.languages.shell = Prism.languages.bash;

// HCL / Terraform
Prism.languages.hcl = {
  comment: [
    { pattern: /\/\/.*/, greedy: true },
    { pattern: /#.*/, greedy: true },
    { pattern: /\/\*[\s\S]*?\*\//, greedy: true },
  ],
  string: { pattern: /"(?:[^"\\]|\\.)*"/, greedy: true },
  keyword:
    /\b(?:resource|data|variable|output|module|provider|terraform|locals|dynamic|for_each|count|depends_on|lifecycle)\b/,
  boolean: /\b(?:true|false)\b/,
  number: /\b\d+(?:\.\d+)?\b/,
  punctuation: /[{}[\]=]/,
  operator: /[=!<>]=?|&&|\|\|/,
  function: { pattern: /\b\w+(?=\s*\()/, greedy: true },
};
Prism.languages.tf = Prism.languages.hcl;

// Docker
Prism.languages.docker = {
  comment: { pattern: /#.*/, greedy: true },
  keyword:
    /\b(?:FROM|AS|RUN|CMD|LABEL|MAINTAINER|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\b/i,
  string: { pattern: /"(?:[^"\\]|\\.)*"/, greedy: true },
  variable: /\$(?:\w+|\{[^}]+\})/,
  operator: /&&|\|\|/,
  punctuation: /[\\[\]]/,
};
Prism.languages.dockerfile = Prism.languages.docker;

// Elixir
Prism.languages.elixir = {
  comment: { pattern: /#.*/, greedy: true },
  string: [
    { pattern: /~[A-Z]"""[\s\S]*?"""/, greedy: true },
    { pattern: /~[a-z]"(?:[^"\\]|\\.)*"/, greedy: true },
    { pattern: /"""[\s\S]*?"""/, greedy: true },
    { pattern: /"(?:[^"\\]|\\.)*"/, greedy: true },
  ],
  atom: { pattern: /:[a-zA-Z_]\w*[?!]?/, greedy: true },
  boolean: /\b(?:true|false|nil)\b/,
  keyword:
    /\b(?:def|defp|defmodule|do|end|if|else|unless|case|cond|when|with|fn|raise|rescue|try|catch|after|for|in|and|or|not|use|import|alias|require|quote|unquote)\b/,
  module: { pattern: /\b[A-Z]\w*(?:\.[A-Z]\w*)*/, greedy: true },
  function: { pattern: /\b\w+(?=[?!]?\s*[(\s])/, greedy: true },
  operator: /\|>|<>|<-|->|=>|=~|~>|::|\.\.\.|&&|\|\||[!=<>]=?|[+\-*/\\^|&]/,
  number: /\b(?:0x[\da-fA-F_]+|0b[01_]+|0o[0-7_]+|\d[\d_]*(?:\.[\d_]+)?(?:[eE][+-]?\d+)?)\b/,
  punctuation: /[()[\]{},;.@#%]/,
};
Prism.languages.ex = Prism.languages.elixir;

// Map file extensions to Prism language identifiers
const EXT_TO_LANG: Record<string, string> = {
  ".py": "python",
  ".sh": "bash",
  ".bash": "bash",
  ".js": "javascript",
  ".jsx": "javascript",
  ".ts": "typescript",
  ".tsx": "typescript",
  ".json": "json",
  ".yaml": "yaml",
  ".yml": "yaml",
  ".toml": "toml",
  ".md": "markdown",
  ".css": "css",
  ".html": "markup",
  ".xml": "markup",
  ".sql": "sql",
  ".tf": "hcl",
  ".hcl": "hcl",
  ".dockerfile": "docker",
  ".ex": "elixir",
  ".exs": "elixir",
  ".heex": "elixir",
  ".rs": "rust",
  ".go": "go",
  ".rb": "ruby",
  ".java": "java",
  ".c": "c",
  ".cpp": "cpp",
  ".h": "c",
};

function getLanguage(filePath: string): string {
  const lower = filePath.toLowerCase();
  // Special filenames
  if (lower.endsWith("dockerfile") || lower.includes("dockerfile")) return "docker";
  if (lower.endsWith("makefile")) return "makefile";
  // Extension lookup
  const dot = lower.lastIndexOf(".");
  if (dot >= 0) {
    const ext = lower.slice(dot);
    return EXT_TO_LANG[ext] ?? "plain";
  }
  return "plain";
}

interface CodeViewerProps {
  code: string;
  filePath: string;
  className?: string;
}

export default function CodeViewer({ code, filePath, className = "" }: CodeViewerProps) {
  const language = getLanguage(filePath);

  return (
    <Highlight theme={themes.nightOwl} code={code.trimEnd()} language={language}>
      {({ style, tokens, getLineProps, getTokenProps }) => (
        <pre
          className={`overflow-x-auto rounded-lg p-4 font-mono text-xs leading-relaxed ${className}`}
          style={{ ...style, background: "transparent" }}
        >
          {tokens.map((line, i) => (
            <div key={i} {...getLineProps({ line })} className="table-row">
              <span className="table-cell select-none pr-4 text-right text-on-surface-dim/40">
                {i + 1}
              </span>
              <span className="table-cell">
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </span>
            </div>
          ))}
        </pre>
      )}
    </Highlight>
  );
}
