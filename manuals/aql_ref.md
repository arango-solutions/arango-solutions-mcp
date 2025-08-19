# AQL language reference

AQL is a descriptive query language for ArangoDB, which is a multi-model
database. "Multi-model" here says that data can be JSON documents or
property graphs, which are also represented by JSON documents.

## Data model

Data of a database is stored in "collections" and there are normal
collections and edge collections. Normal collections store normal
document data and vertex-data (one document per vertex of a graph). Edge
collections store edges of graphs. Each edge points from one vertex to
another.

All documents have three special attributes:

 - `_key` is the primary key and must be a string
 - `_id` is also a string and consists of the collection name, followed by
   a slash and then followed by the primary key.
 - `_rev` is also a string and identifies the **revision** of a document
   uniquely.

The primary key of a document identifies it uniquely in its collections, and
thus the `_id` attribute of a document identifies it uniquely in its database
across all collections.

In edge collections, documents must have another two special attributes, namely:

 - `_from` is the `_id` of the vertex from which the edge originates
 - `_to` is the `_id` of the vertex to which the edge points

Since both `_from` and `_to` contain `_id` values, the vertices of a graph
can be contained in multiple vertex collections.

ArangoDB has sorted indexes on one or multiple fields, geo indexes for
geographical data (geoJSON), multi-dimensional indexes as well as a special
edge index for edge collections. Indexes can constitute unique indexes
(if they are `unique`) and they can be sparse, which means documents which
do not contain a value for an indexed attribute are not indexed at all.

ArangoDB has a builtin search engine, which can be queried using AQL.


## AQL

AQL can do queries for documents and graph queries. This document describes
how AQL works.


### Syntax

Comments in AQL are done as in C++, everything on a line after `//` is a comment,
and everything between a pair of `/*` and `*/` is a comment and such comments
can span multiple lines. Multi-line comments cannot be nested.

AQL has the following key words: `FOR`, `RETURN`, `FILTER`, `SEARCH`, `SORT`,
`LIMIT`, `LET`, `COLLECT`, `WINDOW`,`INSERT`, `UPDATE`, `REPLACE`, `REMOVE`
`UPSERT`, `WITH`, `ASC`, `DESC`, `IN`, `INTO`, `AGGREGATE`, `GRAPH`,
`SHORTEST_PATH`, `K_SHORTEST_PATHS`, `K_PATHS`, `ALL_SHORTEST_PATHS`,
`DISTINCT`, `OUTBOUND`, `INBOUND`, `ANY`, `ALL`, `PRUNE`, `FALSE`, `TRUE`,
`NULL`, `WINDOW`, `AND`, `OR`, `NOT`, `COUNT`, `TO`, `KEEP`, `CURRENT`,
`NEW`, `OLD` and `OPTIONS`.

Keywords are case-insensitive, the rest of AQL is case-sensitive. It is
common practice to write keywords in all caps.

Some keywords are only allowed in certain contexts.

Names in particular are case-sensitive, they are used for collections,
attributes, variables and functions. Names should not be longer than
256 characters. Normal characters in names need not be quoted. To use
a keyword or a string with special characters like `-` as a name, one has
to use backticks as quotes around it.

In the syntax descriptions of the various statements we use the `|` sign
for alternatives and square brackets `[]` for optional parts.


### Data types in AQL

AQL supports the standard JSON data types:

 - `null`
 - boolean with its values `true` and `false`
 - numbers which are essentially doubles
 - strings which are UTF-8 encoded
 - arrays, denoted in square brackets
 - objects, denoted as in JSON, attribute names must be strings, but the
   quotes can be left out if only letters, digits, the underscore and dollar
   signs are used.

Trailing commas in arrays and objects are allowed.

Attribute names can be computed, in which case the expression must be enclosed
in square brackets. This is, for example, a valid object:

```
{ "a": 12, b: null, `return`: "Max", [CONCAT("test/", bar)]: ["a", 1, 2] }
```

and it has attributes `a`, `b`, `return` and `test/xyz` if the value of the
variable `bar` is `xyz`.

Arrays are indexed by numbers using square brackets and array indexes are
0-based. Negative indexes count from the back of the array.

Object attributes are accessed using the normal `.`-notation or index notation
with square brackets and a string value in between.


### Bind parameters

Bind parameters are fed from the outside into a query. A normal bind
parameter starts with an at `@` character and is followed by a name.
Bind parameter names must start with any of the letters a to z (upper
or lower case) or a digit (0 to 9), and can be followed by letters,
digits or underscore symbols.

Using bind parameters, the meaning of an existing query cannot be
changed. Bind parameters can be used everywhere in a query where
literals can be used. Keywords and other language constructs cannot be
replaced by bind values.

For collection names, special bind parameters which start with two at signs
`@@` can be used. These can only be used in places where normally a collection
name can appear.

The replacement of bind parameters happens after parsing in the abstract
syntax tree, so that nasty injections of malicious query code is not
possible.


### Data pipelines

AQL fundamentally describes a data pipeline. Usually data flows from a collection
or index and the subsequent statements do something with the data stream like
filtering, calculations, limiting, joining, sorting or returning. Often,
the order in which a stream is delivered, is undefined, for example when
enumerating the elements of a collection.


### Expressions and operators

Expressions in AQL use the conventional infix notation with operators
and prefix notation for function calls. We have the following comparison
operators:

| Operator   | Description
|:-----------|:-----------
| `==`       | equality
| `!=`       | inequality
| `<`        | less than
| `<=`       | less or equal
| `>`        | greater than
| `>=`       | greater or equal
| `IN`       | test if a value is contained in an array
| `NOT IN`   | test if a value is not contained in an array
| `LIKE`     | tests if a string value matches a pattern
| `NOT LIKE` | tests if a string value does not match a pattern
| `=~`       | tests if a string value matches a regular expression
| `!~`       | tests if a string value does not match a regular expression

Each of the comparison operators returns a boolean value if the comparison can
be evaluated and returns *true* if the comparison evaluates to true, and *false*
otherwise.

The comparison operators accept any data types for the first and second
operands. However, `IN` and `NOT IN` only return a meaningful result if
their right-hand operand is an array. `LIKE` and `NOT LIKE` only execute
if both operands are string values. All four operators do not perform
implicit type casts if the compared operands have different types, i.e.
they test for strict equality or inequality (`0` is different to `"0"`,
`[0]`, `false` and `null` for example).

The `LIKE` operator checks whether its left operand matches the pattern
specified in its right operand. The pattern can consist of regular
characters and wildcards. The supported wildcards are `_` to match a
single arbitrary character, and `%` to match any number of arbitrary
characters. Literal `%` and `_` need to be escaped with a backslash.
Backslashes need to be escaped themselves, which effectively means that
two reverse solidus characters need to precede a literal percent sign or
underscore.

The pattern matching performed by the `LIKE` operator is case-sensitive.

The `NOT LIKE` operator has the same characteristics as the `LIKE`
operator but with the result negated.

Most comparison operators also exist as an *array variant*. In the
array variant, a `==`, `!=`, `>`, `>=`, `<`, `<=`, `IN`, or `NOT IN`
operator is prefixed with an `ALL`, `ANY`, or `NONE` keyword. This
changes the operator's behavior to compare the individual array elements
of the left-hand argument to the right-hand argument. Depending on the
quantifying keyword, all, any, or none of these comparisons need to be
satisfied to evaluate to `true` overall.

You can also combine one of the supported comparison operators with
the special `AT LEAST (<expression>)` operator to require an arbitrary
number of elements to satisfy the condition to evaluate to `true`. You
can use a static number or calculate it dynamically using an expression.

Some examples:

```aql
[ 1, 2, 3 ]  ALL IN  [ 2, 3, 4 ]  // false
[ 1, 2, 3 ]  ALL IN  [ 1, 2, 3 ]  // true
[ 1, 2, 3 ]  NONE IN  [ 3 ]       // false
[ 1, 2, 3 ]  NONE IN  [ 23, 42 ]  // true
[ 1, 2, 3 ]  ANY IN  [ 4, 5, 6 ]  // false
[ 1, 2, 3 ]  ANY IN  [ 1, 42 ]    // true
[ 1, 2, 3 ]  ANY ==  2            // true
[ 1, 2, 3 ]  ANY ==  4            // false
[ 1, 2, 3 ]  ANY >  0             // true
[ 1, 2, 3 ]  ANY <=  1            // true
[ 1, 2, 3 ]  NONE <  99           // false
[ 1, 2, 3 ]  NONE >  10           // true
[ 1, 2, 3 ]  ALL >  2             // false
[ 1, 2, 3 ]  ALL >  0             // true
[ 1, 2, 3 ]  ALL >=  3            // false
["foo", "bar"]  ALL !=  "moo"     // true
["foo", "bar"]  NONE ==  "bar"    // false
["foo", "bar"]  ANY ==  "foo"     // true

[ 1, 2, 3 ]  AT LEAST (2) IN  [ 2, 3, 4 ]  // true
["foo", "bar"]  AT LEAST (1+1) ==  "foo"   // false
```

The following logical operators are supported in AQL:

- `&&` logical and operator
- `||` logical or operator
- `!` logical not/negation operator

AQL also supports the following alternative forms for the logical operators:

- `AND` logical and operator
- `OR` logical or operator
- `NOT` logical not/negation operator

The alternative forms are aliases and functionally equivalent to the regular
operators.

The two-operand logical operators in AQL are executed with short-circuit
evaluation (except if one of the operands is or includes a subquery. In this
case the subquery is pulled out and evaluated before the logical operator).

The result of *logical and* and *logical or* operations can now have any
data type and is not necessarily a boolean value. Passing non-boolean
values to a logical operator is allowed. Any non-boolean operands are
casted to boolean implicitly by the operator, without making the query
abort.

The *conversion to a boolean value* works as follows:
- `null` is converted to `false`
- boolean values remain unchanged
- all numbers unequal to zero are `true`, zero is `false`
- an empty string is `false`, all other strings are `true`
- arrays (`[ ]`) and objects / documents (`{ }`) are `true`, regardless
  of their contents

Arithmetic operators perform an arithmetic operation on two numeric
operands. The result of an arithmetic operation is again a numeric value.

AQL supports the following arithmetic operators:

- `+` addition
- `-` subtraction
- `*` multiplication
- `/` division
- `%` modulus

For exponentiation, there is a function`POW()`.
The syntax `base ** exp` is not supported.

For string concatenation, you must use the `CONCAT()` function].
Combining two strings with a plus operator (`"foo" + "bar"`) does not work!

The arithmetic operators accept operands of any type. Passing
non-numeric values to an arithmetic operator casts the operands
to numbers using the type casting rules applied by the
`TO_NUMBER()` function:

- `null` is converted to `0`
- `false` is converted to `0`, `true` is converted to `1`
- a valid numeric value remains unchanged, but NaN and Infinity are converted to `0`
- string values are converted to a number if they contain a valid string
  representation of a number. Any whitespace at the start or the end of
  the string is ignored. Strings with any other contents are converted
  to the number `0`
- an empty array is converted to `0`, an array with one member is
  converted to the numeric representation of its sole member. Arrays with
  more members are converted to the number `0`.
- objects / documents are converted to the number `0`.

An arithmetic operation that produces an invalid value, such as `1 / 0`
(division by zero), produces a result value of `null`. The query is not
aborted, but you may see a warning.

AQL also supports a ternary operator that can be used for conditional
evaluation. The ternary operator expects a boolean condition as its
first operand, and it returns the result of the second operand if the
condition evaluates to true, and the third operand otherwise.
You may use subqueries as operands.

There is also a shortcut variant of the ternary operator with just two
operands. This variant can be used if the expression for the boolean
condition and the return value should be the same.

In the following example, the expression evaluates to `u.value` if
`u.value` is truthy. Otherwise, a fixed string is given back:

```aql
u.value ? : 'value is null, 0 or not present'
```

The condition (here just `u.value`) is only evaluated once if the second
operand between `?` and `:` is omitted, whereas it would be evaluated
twice in case of `u.value ? u.value : 'value is null'`.

AQL supports expressing simple numeric ranges with the `..` operator.
This operator can be used to easily iterate over a sequence of numeric
values.

The `..` operator produces an array of the integer values in the
defined range, with both bounding values included.

```aql
2010..2013
```

The above example produces the following result:

```json
[ 2010, 2011, 2012, 2013 ]
```

Using the range operator is equivalent to writing an array with the
integer values in the range specified by the bounds of the range. If the
bounds of the range operator are non-integers, they are converted to
integer values first.

In order to access a named attribute from all elements in an array easily, AQL
offers the shortcut operator `[*]` for array variable expansion.

Using the `[*]` operator with an array variable will iterate over all
elements in the array, thus allowing to access a particular attribute of
each element. It is required that the expanded variable is an array. The
result of the `[*]` operator is again an array.

In order to collapse (or flatten) results in nested arrays, AQL provides
the `[**]` operator. It works similar to the `[*]` operator, but
additionally collapses nested arrays.

How many levels are collapsed is determined by the amount of asterisk
characters used. `[**]` collapses one level of nesting - just like
`FLATTEN(array)` or `FLATTEN(array, 1)` would do -, `[***]` collapses
two levels - the equivalent to `FLATTEN(array, 2)` - and so on.


### Operator precedence

The operator precedence in AQL is similar as in other familiar languages
(highest precedence first):

| Operator(s)          | Description
|:---------------------|:-----------
| `::`                 | scope (user-defined AQL functions)
| `[*]`                | array expansion
| `[]`                 | indexed value access (arrays), attribute access (objects)
| `.`                  | attribute access (objects)
| `()`                 | function call
| `!`, `NOT`, `+`, `-` | unary not (logical negation), unary plus, unary minus
| `*`, `/`, `%`        | multiplication, division, modulus
| `+`, `-`             | addition, subtraction
| `..`                 | range operator
| `<`, `<=`, `>=`, `>` | less than, less equal, greater equal, greater than
| `IN`, `NOT IN`       | in operator, not in operator
| `==`, `!=`, `LIKE`, `NOT LIKE`, `=~`, `!~`  | equality, inequality, wildcard match, wildcard non-match, regex match, regex non-match
| `AT LEAST`           | at least modifier (array comparison operator, question mark operator)
| `OUTBOUND`, `INBOUND`, `ANY`, `ALL`, `NONE` | graph traversal directions, array comparison operators, question mark operator
| `&&`, `AND`          | logical and
| `\|\|`, `OR`         | logical or
| `INTO`               | into operator (INSERT / UPDATE / REPLACE / REMOVE / COLLECT operations)
| `WITH`               | with operator (WITH / UPDATE / REPLACE / COLLECT operations)
| `=`                  | variable assignment (LET / COLLECT operations, AGGREGATE / PRUNE clauses)
| `?`, `:`             | ternary operator, object literals
| `DISTINCT`           | distinct modifier (RETURN operations)
| `,`                  | comma separator

The parentheses `(` and `)` can be used to enforce a different operator
evaluation order.


### Functions

Functions can be called at any query position where an expression is allowed.
The general function call syntax is:

```aql
FUNCTIONNAME(arguments)
```

`FUNCTIONNAME` is the name of the function to be called, and `arguments`
is a comma-separated list of function arguments. If a function does not need any
arguments, the argument list can be left empty. However, even if the argument
list is empty, the parentheses around it are still mandatory to make function
calls distinguishable from variable names.

In contrast to collection and variable names, function names are
case-insensitive, i.e. `LENGTH(foo)` and `length(foo)` are equivalent.

Below is a comprehensive list of all AQL functions organized by category:

#### Array Functions

- `APPEND(anyArray, values, unique) → newArray` - Add all elements of an array to another array
- `CONTAINS_ARRAY(anyArray, search, returnIndex) → match` - Alias for `POSITION()`
- `COUNT(anyArray) → length` - Alias for `LENGTH()`
- `COUNT_DISTINCT(anyArray) → number` - Get the number of distinct elements in an array
- `COUNT_UNIQUE(anyArray) → number` - Alias for `COUNT_DISTINCT()`
- `FIRST(anyArray) → firstElement` - Get the first element of an array
- `FLATTEN(anyArray, depth) → flatArray` - Turn an array of arrays into a flat array
- `INTERLEAVE(array1, array2, ... arrayN) → newArray` - Interleave elements from multiple arrays
- `INTERSECTION(array1, array2, ... arrayN) → newArray` - Return the intersection of all arrays
- `JACCARD(array1, array2) → jaccardIndex` - Calculate the Jaccard index of two arrays
- `LAST(anyArray) → lastElement` - Get the last element of an array
- `LENGTH(anyArray) → length` - Determine the number of elements in an array
- `MINUS(array1, array2, ... arrayN) → newArray` - Return the difference of all arrays
- `NTH(anyArray, position) → nthElement` - Get the element of an array at a given position
- `OUTERSECTION(array1, array2, ... arrayN) → newArray` - Return values that occur only once across all arrays
- `POP(anyArray) → newArray` - Remove the last element of array
- `POSITION(anyArray, search, returnIndex) → position` - Return the position of a value in an array
- `PUSH(anyArray, value, unique) → newArray` - Append a value to an array
- `REMOVE_NTH(anyArray, position) → newArray` - Remove the element at a given position from an array
- `REMOVE_VALUE(anyArray, value, limit) → newArray` - Remove all occurrences of a value from an array
- `REMOVE_VALUES(anyArray, values) → newArray` - Remove all occurrences of any values from an array
- `REVERSE(anyArray) → newArray` - Return an array with elements in reverse order
- `SHIFT(anyArray) → newArray` - Remove the first element of an array
- `SLICE(anyArray, start, length) → newArray` - Extract a slice from an array
- `SORTED(anyArray) → newArray` - Return a sorted array
- `SORTED_UNIQUE(anyArray) → newArray` - Return a sorted array with unique elements
- `UNION(array1, array2, ... arrayN) → newArray` - Return the union of all arrays
- `UNION_DISTINCT(array1, array2, ... arrayN) → newArray` - Return the union of all arrays with unique elements
- `UNIQUE(anyArray) → newArray` - Return an array with unique elements
- `UNSHIFT(anyArray, value, unique) → newArray` - Add a value to the beginning of an array

#### String Functions

- `CHAR_LENGTH(str) → length` - Return the number of characters in a string
- `CONCAT(value1, value2, ... valueN) → str` - Concatenate values into a string
- `CONCAT_SEPARATOR(separator, value1, value2, ... valueN) → joinedString` - Concatenate strings with a separator
- `CONTAINS(text, search, returnIndex) → match` - Check whether a string is contained in another string
- `COUNT(str) → length` - Alias for `LENGTH()`
- `CRC32(text) → hash` - Calculate the CRC32 checksum for a string
- `ENCODE_URI_COMPONENT(value) → encodedString` - Return the URI component-encoded string
- `FIND_FIRST(text, search, start, end) → position` - Return the position of the first occurrence of a string
- `FIND_LAST(text, search, start, end) → position` - Return the position of the last occurrence of a string
- `FNV64(text) → hash` - Calculate the FNV-1A 64 bit hash for a string
- `IPV4_FROM_NUMBER(numericAddress) → stringAddress` - Convert a numeric IPv4 address to string
- `IPV4_TO_NUMBER(stringAddress) → numericAddress` - Convert an IPv4 address string to numeric
- `JSON_PARSE(text) → value` - Parse a JSON string and return the corresponding value
- `JSON_STRINGIFY(value) → text` - Stringify a value into a JSON string
- `LEFT(text, length) → substring` - Return the leftmost characters of a string
- `LENGTH(str) → length` - Return the character length of a string
- `LEVENSHTEIN_DISTANCE(value1, value2) → distance` - Calculate the Levenshtein distance between two strings
- `LIKE(text, search, caseInsensitive) → bool` - Check whether a string matches a pattern
- `LOWER(text) → lowerCaseText` - Convert a string to lower case
- `LTRIM(text, chars) → strippedString` - Remove leading whitespace or characters
- `MD5(text) → hash` - Calculate the MD5 checksum of a string
- `NORMALIZE_STRING(text, form) → normalizedText` - Return the normalized form of a string
- `RANDOM_TOKEN(length) → randomString` - Generate a random token string
- `REGEX_MATCHES(text, regex, caseInsensitive) → stringArray` - Return the matches of a regular expression
- `REGEX_REPLACE(text, search, replacement, caseInsensitive) → newText` - Replace text using regular expressions
- `REGEX_SPLIT(text, splitExpression, caseInsensitive, limit) → stringArray` - Split a string using a regular expression
- `REGEX_TEST(text, search, caseInsensitive) → bool` - Check whether a string matches a regular expression
- `REVERSE(text) → reversedText` - Return a string with characters in reverse order
- `RIGHT(text, length) → substring` - Return the rightmost characters of a string
- `RTRIM(text, chars) → strippedString` - Remove trailing whitespace or characters
- `SHA1(text) → hash` - Calculate the SHA1 checksum of a string
- `SHA256(text) → hash` - Calculate the SHA256 checksum of a string
- `SHA512(text) → hash` - Calculate the SHA512 checksum of a string
- `SOUNDEX(text) → soundexString` - Return the Soundex fingerprint of a string
- `SPLIT(text, separator, limit) → stringArray` - Split a string into an array
- `STARTS_WITH(text, prefix) → bool` - Check whether a string starts with a prefix
- `SUBSTRING(text, offset, length) → substring` - Return a substring
- `SUBSTITUTE(text, search, replace, limit) → newText` - Replace search values in a string
- `TOKENS(input, analyzer) → tokenArray` - Split a string into an array of tokens
- `TRANSLATE(text, searchChars, replaceChars) → newText` - Replace characters in a string
- `TRIM(text, type) → strippedString` - Remove leading and/or trailing whitespace
- `UPPER(text) → upperCaseText` - Convert a string to upper case
- `UUID() → uuidString` - Return a universally unique identifier

#### Numeric Functions

- `ABS(value) → unsignedValue` - Return the absolute value of a number
- `ACOS(value) → num` - Return the arccosine of a value
- `ASIN(value) → num` - Return the arcsine of a value
- `ATAN(value) → num` - Return the arctangent of a value
- `ATAN2(y, x) → num` - Return the arctangent of the quotient of y and x
- `AVERAGE(numArray) → mean` - Return the average of values in an array
- `AVG(numArray) → mean` - Alias for `AVERAGE()`
- `CEIL(value) → roundedValue` - Return the ceiling of a number
- `COS(value) → num` - Return the cosine of a value
- `COSINE_SIMILARITY(x, y) → num` - Return the cosine similarity between two vectors
- `DECAY_GAUSS(value, origin, scale, offset, decay) → score` - Calculate Gaussian decay score
- `DECAY_EXP(value, origin, scale, offset, decay) → score` - Calculate exponential decay score
- `DECAY_LINEAR(value, origin, scale, offset, decay) → score` - Calculate linear decay score
- `DEGREES(rad) → num` - Convert radians to degrees
- `EXP(value) → num` - Return Euler's constant raised to the power of value
- `EXP2(value) → num` - Return 2 raised to the power of value
- `FLOOR(value) → roundedValue` - Return the floor of a number
- `L1_DISTANCE(x, y) → num` - Return the Manhattan distance between two vectors
- `L2_DISTANCE(x, y) → num` - Return the Euclidean distance between two vectors
- `LOG(value) → num` - Return the natural logarithm of a value
- `LOG2(value) → num` - Return the base 2 logarithm of a value
- `LOG10(value) → num` - Return the base 10 logarithm of a value
- `MAX(anyArray) → max` - Return the greatest element of an array
- `MEDIAN(numArray) → median` - Return the median value of an array
- `MIN(anyArray) → min` - Return the smallest element of an array
- `PERCENTILE(numArray, n, method) → percentile` - Return the nth percentile of values
- `PI() → pi` - Return the value of pi
- `POW(base, exp) → num` - Return base raised to the power of exp
- `RADIANS(deg) → num` - Convert degrees to radians
- `RAND() → randomNumber` - Return a random number between 0 and 1
- `RANGE(start, stop, step) → numArray` - Return an array of numbers in a range
- `ROUND(value) → roundedValue` - Round a number to the nearest integer
- `SIN(value) → num` - Return the sine of a value
- `SQRT(value) → num` - Return the square root of a value
- `STDDEV_POPULATION(numArray) → num` - Return the population standard deviation
- `STDDEV_SAMPLE(numArray) → num` - Return the sample standard deviation
- `SUM(numArray) → num` - Return the sum of all values in an array
- `TAN(value) → num` - Return the tangent of a value
- `VARIANCE_POPULATION(numArray) → num` - Return the population variance
- `VARIANCE_SAMPLE(numArray) → num` - Return the sample variance

#### Date Functions

- `DATE_NOW() → timestamp` - Get the current unix time as numeric timestamp
- `DATE_ISO8601(date) → dateString` - Return an ISO 8601 date time string
- `DATE_TIMESTAMP(date) → timestamp` - Create a timestamp value from date
- `IS_DATESTRING(value) → bool` - Check if a string is suitable for date interpretation
- `DATE_DAYOFWEEK(date, timezone) → weekdayNumber` - Return the weekday number of date
- `DATE_YEAR(date, timezone) → year` - Return the year of date
- `DATE_MONTH(date, timezone) → month` - Return the month of date
- `DATE_DAY(date, timezone) → day` - Return the day of date
- `DATE_HOUR(date, timezone) → hour` - Return the hour of date
- `DATE_MINUTE(date, timezone) → minute` - Return the minute of date
- `DATE_SECOND(date) → second` - Return the second of date
- `DATE_MILLISECOND(date) → millisecond` - Return the millisecond of date
- `DATE_DAYOFYEAR(date, timezone) → dayOfYear` - Return the day of year
- `DATE_ISOWEEK(date, timezone) → weekNumber` - Return the ISO week number
- `DATE_ISOWEEKYEAR(date, timezone) → weekYear` - Return the ISO week year
- `DATE_LEAPYEAR(date, timezone) → bool` - Check if the year is a leap year
- `DATE_QUARTER(date, timezone) → quarter` - Return the quarter of date
- `DATE_DAYS_IN_MONTH(date, timezone) → daysInMonth` - Return the number of days in month
- `DATE_TRUNC(date, unit, timezone) → truncatedDate` - Truncate date to specified unit
- `DATE_ROUND(date, amount, unit, timezone) → roundedDate` - Round date to specified unit
- `DATE_ADD(date, amount, unit, timezone) → newDate` - Add time to date
- `DATE_SUBTRACT(date, amount, unit, timezone) → newDate` - Subtract time from date
- `DATE_DIFF(date1, date2, unit, asFloat, timezone) → diff` - Calculate difference between dates
- `DATE_COMPARE(date1, date2, unitRangeStart, unitRangeEnd, timezone) → comparison` - Compare two dates
- `DATE_FORMAT(date, format, timezone) → formattedDate` - Format date as string

#### Document/Object Functions

- `ATTRIBUTES(document, removeSystemAttrs, sort) → strArray` - Return attribute keys of document
- `COUNT(doc) → attrCount` - Alias for `LENGTH()`
- `ENTRIES(document) → pairArray` - Return attributes as key-value pairs
- `HAS(document, attributeName) → isPresent` - Test whether an attribute is present
- `IS_SAME_COLLECTION(collectionName, documentIdentifier) → isSame` - Test collection membership
- `KEEP(document, attributeName1, ...) → doc` - Keep only specified attributes
- `KEEP_RECURSIVE(document, attributeName1, ...) → doc` - Recursively keep specified attributes
- `KEYS(document, removeSystemAttrs, sort) → strArray` - Alias for `ATTRIBUTES()`
- `LENGTH(doc) → attrCount` - Determine number of attribute keys
- `MATCHES(document, examples, returnIndex) → match` - Compare document against examples
- `MERGE(document1, document2, ...) → mergedDocument` - Merge multiple documents
- `MERGE_RECURSIVE(document1, document2, ...) → mergedDocument` - Recursively merge documents
- `PARSE_IDENTIFIER(documentHandle) → docIdentifier` - Parse document handle into components
- `TRANSLATE(document, lookupDocument, defaultValue) → newDocument` - Translate attribute values
- `UNSET(document, attributeName1, ...) → doc` - Remove specified attributes
- `UNSET_RECURSIVE(document, attributeName1, ...) → doc` - Recursively remove specified attributes
- `VALUES(document, removeSystemAttrs) → valueArray` - Return attribute values
- `ZIP(keys, values) → doc` - Create document from key and value arrays

#### Geo Functions

- `DISTANCE(latitude1, longitude1, latitude2, longitude2) → distance` - Calculate distance between coordinates
- `GEO_AREA(geoJsonObject) → area` - Calculate area of a GeoJSON object
- `GEO_CONTAINS(geoJsonA, geoJsonB) → bool` - Test if geometry A contains geometry B
- `GEO_DISTANCE(geoJsonA, geoJsonB, ellipsoid) → distance` - Calculate distance between geometries
- `GEO_EQUALS(geoJsonA, geoJsonB) → bool` - Test if geometries are equal
- `GEO_INTERSECTS(geoJsonA, geoJsonB) → bool` - Test if geometries intersect
- `GEO_IN_RANGE(geoJsonA, geoJsonB, low, high, includeLow, includeHigh) → bool` - Test if distance is in range
- `GEO_LINESTRING(points) → geoJsonLineString` - Create a GeoJSON LineString
- `GEO_MULTILINESTRING(lineStrings) → geoJsonMultiLineString` - Create a GeoJSON MultiLineString
- `GEO_MULTIPOINT(points) → geoJsonMultiPoint` - Create a GeoJSON MultiPoint
- `GEO_MULTIPOLYGON(polygons) → geoJsonMultiPolygon` - Create a GeoJSON MultiPolygon
- `GEO_POINT(longitude, latitude) → geoJsonPoint` - Create a GeoJSON Point
- `GEO_POLYGON(points) → geoJsonPolygon` - Create a GeoJSON Polygon
- `IS_IN_POLYGON(points, latitude, longitude, useLonLat) → bool` - Test if point is in polygon
- `NEAR(coll, latitude, longitude, limit, distanceName) → docArray` - Find documents near coordinates
- `WITHIN(coll, latitude, longitude, radius, distanceName) → docArray` - Find documents within radius
- `WITHIN_RECTANGLE(coll, latitude1, longitude1, latitude2, longitude2) → docArray` - Find documents in rectangle

#### Type Check and Cast Functions

- `TO_BOOL(value) → bool` - Convert value to boolean
- `TO_NUMBER(value) → number` - Convert value to number
- `TO_STRING(value) → str` - Convert value to string
- `TO_ARRAY(value) → array` - Convert value to array
- `TO_LIST(value) → array` - Alias for `TO_ARRAY()`
- `IS_NULL(value) → bool` - Check whether value is null
- `IS_BOOL(value) → bool` - Check whether value is boolean
- `IS_NUMBER(value) → bool` - Check whether value is number
- `IS_STRING(value) → bool` - Check whether value is string
- `IS_ARRAY(value) → bool` - Check whether value is array
- `IS_LIST(value) → bool` - Alias for `IS_ARRAY()`
- `IS_OBJECT(value) → bool` - Check whether value is object
- `IS_DOCUMENT(value) → bool` - Alias for `IS_OBJECT()`
- `IS_DATESTRING(value) → bool` - Check whether value is date string
- `IS_IPV4(value) → bool` - Check whether value is IPv4 address
- `IS_KEY(value) → bool` - Check whether value is valid document key
- `TYPENAME(value) → typeName` - Return the data type name of value

#### Bit Functions

- `BIT_AND(numbersArray) → result` - Bitwise AND operation
- `BIT_CONSTRUCT(positionsArray) → result` - Construct number from bit positions
- `BIT_DECONSTRUCT(number) → positionsArray` - Deconstruct number into bit positions
- `BIT_FROM_STRING(bitstring) → number` - Convert bitstring to number
- `BIT_NEGATE(number, bits) → result` - Bitwise negate operation
- `BIT_OR(numbersArray) → result` - Bitwise OR operation
- `BIT_POPCOUNT(number) → result` - Count number of set bits
- `BIT_SHIFT_LEFT(number, shift, bits) → result` - Bitwise left shift
- `BIT_SHIFT_RIGHT(number, shift, bits) → result` - Bitwise right shift
- `BIT_TEST(number, position) → result` - Test if bit is set
- `BIT_TO_STRING(number) → bitstring` - Convert number to bitstring
- `BIT_XOR(numbersArray) → result` - Bitwise XOR operation

#### Miscellaneous Functions

- `FIRST_DOCUMENT(alternative, ...) → doc` - Return first alternative that is a document
- `FIRST_LIST(alternative, ...) → list` - Return first alternative that is an array
- `MIN_MATCH(expr1, ... exprN, minMatchCount) → fulfilled` - Match minimum number of expressions
- `NOT_NULL(alternative, ...) → value` - Return first non-null alternative
- `CHECK_DOCUMENT(document) → checkResult` - Check if document is valid
- `COLLECTION_COUNT(coll) → count` - Determine number of documents in collection
- `COLLECTIONS() → docArray` - Return array of collections
- `CURRENT_DATABASE() → databaseName` - Return name of current database
- `CURRENT_USER() → userName` - Return name of current user
- `DECODE_REV(revision) → details` - Decompose revision string into components
- `DOCUMENT(collection, key) → doc` - Look up document by key
- `HASH(value) → hashValue` - Calculate hash value
- `LENGTH(coll) → count` - Count documents in collection
- `NOOPT(value) → value` - Prevent query optimization for expression
- `PASSTHRU(value) → value` - Return value unchanged
- `PREGEL_RESULT(jobId) → result` - Return result of Pregel algorithm
- `SLEEP(seconds) → null` - Wait for specified time
- `V8(code) → result` - Execute JavaScript code
- `VERSION() → versionInfo` - Return ArangoDB version information
- `WARN(message, data) → null` - Emit warning message

#### ArangoSearch Functions

- `ANALYZER(expr, analyzer) → retVal` - Set analyzer for search expression
- `BOOST(expr, boost) → retVal` - Override boost in search context
- `EXISTS(path, type) → bool` - Check if attribute exists in View context
- `PHRASE(attribute, phrase, analyzer) → bool` - Search for phrase in attribute
- `STARTS_WITH(attribute, prefix) → bool` - Search for prefix in attribute
- `MIN_MATCH(expr1, ... exprN, minMatchCount) → fulfilled` - Minimum match in search context
- `BM25(doc, k, b) → score` - Calculate BM25 relevance score
- `TFIDF(doc, normalize) → score` - Calculate TF-IDF relevance score
- `TOKENS(input, analyzer) → tokenArray` - Split input into tokens using analyzer

#### Fulltext Functions

- `FULLTEXT(coll, attribute, query, limit) → docArray` - Search collection with fulltext index

#### Vector Functions

- `APPROX_NEAR_COSINE(vector1, vector2, options) → similarity` - Calculate approximate cosine similarity
- `APPROX_NEAR_L2(vector1, vector2, options) → similarity` - Calculate approximate L2 distance

### Returning values

The `RETURN` statement tells a query what it should return. Every AQL
query returns a list of things, so the query

```aql
RETURN 42
```

returns a list with only one element 42. Arbitrary JSON objects can be returned.

`RETURN` is also used in subqueries.


### Accessing collections

One produces a stream of the documents which are in a collection with the
`FOR` statement:

```aql
FOR doc IN coll
```

essentially produces a stream of all the documents in the collection named
`coll` and binds the name `doc` to each one, one after another. That is,
the `FOR` statement opens a new scope for the variable `doc`.

More exactly, the `FOR` statement produces its stream **once for each
incoming item** from the query context before the statement. At the
beginning of a query, there is an implicit stream which produces a singleton
object without data.

Thus, the query

```aql
FOR a IN coll1
  FOR b IN coll2
    RETURN {doca: a, docb: b}
```

produces a stream of pairs, enumerating the cartesian product of the documents
in collection `coll1` and `coll2`.

Note that for accessing a single document in some collection there is also
the `DOCUMENT` function, which has these two syntaxes:

```aql
DOCUMENT(collection, key)
DOCUMENT(id)
```

In the first form, the first argument is the collection name and the second
a primary key or id. In the second form the id of the document is given.

It is recommended to use subqueries with the FOR operation and filters
over DOCUMENT() whenever the collections are known in advance,
especially for joins, because they perform better, you can add
additional filters, and combine it with sorting to get an array of
documents in a guaranteed order.

Queries that use the DOCUMENT() function cannot be cached, each lookup
is executed as a single operation, the lookups need to be executed on
Coordinators for sharded collections in cluster deployments, and only
primary indexes and no projections can be utilized.

### Filtering

One can filter a stream with the `FILTER` statement. It is followed by
a single expression which let's an item through if it evaluates to `true`
and discards the item, if it evaluates to `false` or `null`. For example:

```aql
FOR doc IN coll
  FILTER doc.name >= "X"
  RETURN doc
```

will return a stream of all those documents in the collection `coll` whose
attribute `name` has a value which is greater or equal to the string `X`.

The FILTER statement is also used to express inner joins. For example:

```aql
FOR a IN coll1
  FOR b IN coll2
    FILTER a.foreign == b._key
    RETURN {doca: a, docb: b}
```

computes the set of all pairs (`a`, `b`) of documents such that `a` comes from
collection `coll1`, `b` comes from `coll2` and the `foreign` attribute
of `a` is equal to the primary key `_key` of document `b`, thus, this
is an inner join.


### Limiting

The `LIMIT` statement has two purposes: Limiting the number of items
going through and skipping items. The statement

```aql
LIMIT 10
```

will only let through the first 10 items from the incoming stream to produce
the outcoming stream. The statement

```aql
LIMIT 100, 10
```

will skip the first 100 items and then deliver the next 10 before cutting
the stream. Note that the order of elements in a stream is only well-defined
if some sorting statement is used, for example the documents from a collection
coming from the `FOR` statement come in an undefined order.


### Sorting

The `SORT` statement sorts the incoming stream before handing on all items.
One can give a list of expressions, separated by commas, by which sorting is
done in a lexicographic fashion. For each expression, one can either append
the keyword `ASC` for ascending order or `DESC` for descending order, if
omitted, ascending order is chosen.

Note that AQL defines a total order on the set of all JSON values, in which

null  <  bool  <  number  <  string  <  array <  object

Arrays are sorted lexicographically and objects are also sorted lexicographically
in the following way: For each object, the keys are sorted and then the system
compares the values key by key. If a key is not bound in one object, its value
counts as `null`. The first key where a difference in values is spotted,
decides about the sorting order.

Example:

```aql
SORT doc.name ASC, doc.firstName DESC
```

This will sort first by the `name` attribute (ascending) and then, for equal
names, by `firstName` in a descending fashion.

**Warning**: In general, a SORT statement has to pull the complete
input stream, sort it in RAM, and then hand it on in sort order, so this
can be memory consuming. However, if the query optimizer notices that an
index can be used and so the incoming stream of the SORT statement **is already**
sorted, then the `SORT` statement comes for free and does not have to pull
the whole stream before sending the first item on. So the SORT statement
can also be used to indicate that some index on some attribute should be used.

For example:

```aql
FOR doc IN coll
  SORT doc.name
  RETURN doc
```

indicates that the documents in the collection `coll` should be sorted by the
values of the `name` attribute. If the collection has a sorted index on
`name`, then this index is used, the stream flowing into the `SORT` statement
is already sorted by `name` and the `SORT` statement comes for free.


### Assigning variables

The `LET` statement is used to assign a variable. Variables are immutable
and the scope of the defined variable is simply everything after the
`LET` statement. For example:

```aql
LET a = CONCAT(doc.name, ", ", doc.firstName)
```

assigns the concatenation of the value of the `name` attribute, the string
", " and the value of the `firstName` attribute to the variable `a`, which
can then be used in statements below.

Variables cannot be reassigned or mutated in any way.

`LET` statements can be used to bind results from subqueries (see below)
to variables, as in this example:

```aql
LET l = (FOR doc IN coll FILTER doc.name >= "X" RETURN doc)
```

will bind the variable `l` to the list of documents in collection `coll`
whose `name` attribute is greater or equal to `X`.

The `LET` statement allows object and array destructuring:

Wrap the target assignment variables on the left-hand side of a `LET` operation
in square brackets and separate them with commas, like an array. This assigns
the first array element to the first variable, the second element to the second
variable, and so on:

```aql
LET [x, y] = [1, 2, 3]
```

The above example assigns the value `1` to variable `x` and the value `2` to
variable `y`. The value `3` is not assigned to a variable and thus ignored.

You can skip the assignment of unneeded array values by leaving out variable
names but keeping the commas:

```aql
LET [, y, z] = [1, 2, 3]
```

The above example assigns the value `2` to variable `y` and the value `3` to
variable `z`. The first array element with value `1` is not assigned to any
variable and thus ignored.

If there are more variables assigned than there are array elements, the
target variables that are mapped to non-existing array elements are
populated with a value of `null`. The assigned target variables also
receive a value of `null` if the array destructuring is used on anything
other than an array.

You can also destructure nested arrays.

Object destructuring lets you assign object attributes to one or
multiple variables with a single `LET` operation. You can also
destructure objects as part of regular `FOR` loops.

Wrap the target assignment variables on the left-hand side of a `LET`
operation in curly braces and separate them with commas, similar to an
object. The attributes of the source object on the right-hand side are
mapped to the target variables by name:

```aql
LET { name, age } = { vip: true, age: 39, name: "Luna Miller" }
```

The above example assigns the value `"Luna Miller"` of the `name` attribute to
the `name` variable. The value `39` of the `age` attribute is assigned to the
`age` variable. The `vip` attribute of the source object is ignored.

If you specify target variables with no matching attributes in the
source object, or if you try the object destructuring on anything other
than an object, then the variables receive a value of `null`.

You can also destructure objects with sub-attributes.

You can mix object and array destructuring.


### Aggregation with `COLLECT`

Aggregations are done with the `COLLECT` statement. Essentially, the
`COLLECT` statement takes the incoming stream of items and groups them
by the value of a given expression in the input. The resulting groups
of items can be assigned to a "groupsVariable" and the statement
produces one result item per group. With the additional `AGGREGATE`
statement an "aggregationExpression" can be specified.

There are several syntax variants for `COLLECT` operations:

```
COLLECT variableName = expression
COLLECT variableName = expression INTO groupsVariable
COLLECT variableName = expression INTO groupsVariable = projectionExpression
COLLECT variableName = expression INTO groupsVariable KEEP keepVariable
COLLECT variableName = expression WITH COUNT INTO countVariable
COLLECT variableName = expression AGGREGATE variableName = aggregateExpression
COLLECT variableName = expression AGGREGATE variableName = aggregateExpression INTO groupsVariable
COLLECT AGGREGATE variableName = aggregateExpression
COLLECT AGGREGATE variableName = aggregateExpression INTO groupsVariable
COLLECT WITH COUNT INTO countVariable
```

All variants can optionally end with an `OPTIONS { ... }` clause.

The `COLLECT` operation eliminates all variables in the current
scope. After a `COLLECT`, only the variables introduced by `COLLECT`
itself are available.

The first form above only groups, the second stores for each group the
list of items in the group into the "groupsVariable".

`COLLECT` also allows specifying multiple group criteria. Individual group
criteria can be separated by commas.

The third form of `COLLECT` allows rewriting the contents of the
"groupsVariable" using an arbitrary "projectionExpression":

```aql
FOR u IN users
  COLLECT country = u.country, city = u.city INTO groups = u.name
  RETURN {
    "country" : country,
    "city" : city,
    "userNames" : groups
  }
```

In the above example, the "projectionExpression" is only `u.name`.
Therefore, only this attribute is copied into the "groupsVariable" for
each document. This is probably much more efficient than copying all
variables from the scope into the "groupsVariable" as it would happen
without a "projectionExpression".

`COLLECT` also provides an optional `KEEP` clause that can be used to
control which variables will be copied into the variable created by
`INTO`. If no `KEEP` clause is specified, all variables from the scope
will be copied as sub-attributes into the "groupsVariable". This is
safe but can have a negative impact on performance if there are many
variables in scope or the variables contain massive amounts of data.

`KEEP` is only valid in combination with `INTO`. Only valid variable
names can be used in the `KEEP` clause. `KEEP` supports the
specification of multiple variable names.

`COLLECT` also provides a special `WITH COUNT` clause that can be used to
determine the number of group members efficiently.

The simplest form just returns the number of items that made it into the
`COLLECT`:

```aql
FOR u IN users
  COLLECT WITH COUNT INTO length
  RETURN length
```

The above is equivalent to, but less efficient than:

```aql
RETURN LENGTH(users)
```

The `WITH COUNT` clause can also be used to efficiently count the number
of items in each group:

```aql
FOR u IN users
  COLLECT age = u.age WITH COUNT INTO length
  RETURN {
    "age" : age,
    "count" : length
  }
```

The `WITH COUNT` clause can only be used together with an `INTO` clause.

You can use `COLLECT` operations with an `AGGREGATE` clause to aggregate the
data per group, such as determining the minimum, maximum, and average values,
the sums, and more.

To only determine the group lengths, you can use the `WITH COUNT INTO` variant of
`COLLECT` as described above. However, you can also express the same as an aggregation:

```aql
FOR u IN users
  COLLECT age = u.age AGGREGATE length = COUNT()  // or SUM(1)
  RETURN {
    "age" : age,
    "count" : length
  }
```

If you perform calculations on the results of a `COLLECT` operation, you may be
able rewrite them to `COLLECT ... AGGREGATE`. The following example shows a
post-aggregation where the calculation happens after grouping:

```aql
FOR u IN users
  COLLECT ageGroup = FLOOR(u.age / 5) * 5 INTO g
  RETURN {
    "ageGroup" : ageGroup,
    "minAge" : MIN(g[*].u.age),
    "maxAge" : MAX(g[*].u.age)
  }
```

The above however requires storing all group values during the collect operation for
all groups, which can be inefficient.

The special `AGGREGATE` variant of `COLLECT` allows building the aggregate values
incrementally during the collect operation, and is therefore often more efficient.

With the `AGGREGATE` variant, the above query becomes the following:

```aql
FOR u IN users
  COLLECT ageGroup = FLOOR(u.age / 5) * 5
  AGGREGATE minAge = MIN(u.age), maxAge = MAX(u.age)
  RETURN {
    ageGroup,
    minAge,
    maxAge
  }
```

The `AGGREGATE` keyword can only be used after the `COLLECT` keyword.
If used, it must directly follow the declaration of the grouping keys.
If no grouping keys are used, it must follow the `COLLECT` keyword
directly:

```aql
FOR u IN users
  COLLECT AGGREGATE minAge = MIN(u.age), maxAge = MAX(u.age)
  RETURN {
    minAge,
    maxAge
  }
```

Only specific expressions are allowed on the right-hand side of each
`AGGREGATE` assignment:

- On the top level, an aggregate expression must be a call to one of the
  supported aggregation functions:
  - `LENGTH()` / `COUNT()`
  - `MIN()`
  - `MAX()`
  - `SUM()`
  - `AVERAGE()` / `AVG()`
  - `STDDEV_POPULATION()` / `STDDEV()`
  - `STDDEV_SAMPLE()`
  - `VARIANCE_POPULATION()` / `VARIANCE()`
  - `VARIANCE_SAMPLE()`
  - `UNIQUE()`
  - `SORTED_UNIQUE()`
  - `COUNT_DISTINCT()` / `COUNT_UNIQUE()`
  - `BIT_AND()`
  - `BIT_OR()`
  - `BIT_XOR()`
  - `PUSH()` (introduced in v3.12.4)

An aggregate expression must not refer to variables introduced by the
`COLLECT` itself.

#### `COLLECT` options

You can disable the `use-index-for-collect` optimization for individual
`COLLECT` operations by setting this option to `true`.

```aql
COLLECT ... OPTIONS { disableIndex: true }
```

The optimization improves the scanning for distinct values using
`COLLECT` if a usable persistent index is present. It is automatically
disabled if the selectivity is high, i.e. there are many different
values, or if there is filtering or an `INTO` or `AGGREGATE` clause.

There are two variants of `COLLECT` that the optimizer can choose from:
the *sorted* and the *hash* variant. The `method` option can be used in a
`COLLECT` statement to inform the optimizer about the preferred method,
`"sorted"` or `"hash"`.

```aql
COLLECT ... OPTIONS { method: "sorted" }
```

If no method is specified by the user, then the optimizer will create
a plan that uses the *sorted* method, and an additional plan using the
*hash* method if the `COLLECT` statement qualifies for it.

If the method is explicitly set to *sorted*, then the optimizer will
always use the *sorted* variant of `COLLECT` and not even create a
plan using the *hash* variant. If it is explicitly set to *hash*, then
the optimizer will create a plan using the *hash* method **only if the
`COLLECT` statement qualifies**. Not all `COLLECT` statements can use
the *hash* method, in particular ones that do not perform any grouping.
In case the `COLLECT` statement qualifies, there will only be one plan
that uses the *hash* method. Otherwise, the optimizer will default to
the *sorted* method.

The *sorted* method requires its input to be sorted by the group criteria
specified in the `COLLECT` clause. To ensure correctness of the result, the
optimizer will automatically insert a `SORT` operation into the query in front
of the `COLLECT` statement. The optimizer may be able to optimize away that
`SORT` operation later if a sorted index is present on the group criteria.

In case a `COLLECT` statement qualifies for using the *hash* variant,
the optimizer will create an extra plan for it at the beginning of the
planning phase. In this plan, no extra `SORT` statement will be added in
front of the `COLLECT`. This is because the *hash* variant of `COLLECT`
does not require sorted input. Instead, a `SORT` statement will be added
after the `COLLECT` to sort its output. This `SORT` statement may be
optimized away again in later stages.

If the sort order of the `COLLECT` is irrelevant to the user, adding
the extra instruction `SORT null` after the `COLLECT` will allow the
optimizer to remove the sorts altogether:

```aql
FOR u IN users
  COLLECT age = u.age
  SORT null  /* note: will be optimized away */
  RETURN age
```

Which `COLLECT` variant is used by the optimizer if no preferred method
is set explicitly depends on the optimizer's cost estimations. The
created plans with the different `COLLECT` variants will be shipped
through the regular optimization pipeline. In the end, the optimizer
will pick the plan with the lowest estimated total cost as usual.

In general, the *sorted* variant of `COLLECT` should be preferred in
cases when there is a sorted index present on the group criteria. In
this case the optimizer can eliminate the `SORT` operation in front of
the `COLLECT`, so that no `SORT` will be left.

If there is no sorted index available on the group criteria, the
up-front sort required by the *sorted* variant can be expensive. In this
case it is likely that the optimizer will prefer the *hash* variant of
`COLLECT`, which does not require its input to be sorted.


### WITH statements

A `WITH` statement has the sole purpose to declare that the collections
in a comma separated list of collections are used in the query. This is
relevant for graph traversals where only the edge collections are
mentioned and it is a priori unclear which vertex collections can occur
during the graph traversal. All occuring vertex collections must be
named in a `WITH` statement, such that this is known a priori.


### List iteration using `FOR`

The `FOR` statement can also be used to iterate over a list (array). This
can either be given explicitly or via a bind parameter or be stored in
a variable (for example coming from the result of a subquery).


### Destructuring in `FOR` statements

In `FOR` statements the same destructuring operations for arrays and objects
are allowed as in the LET statement. Here is an example:

```aql
FOR [a, b] IN [[1,2], [2,3], [3,4]]
```


### Subqueries

Wherever an expression is allowed in AQL, a subquery can be placed. A subquery
is a query part that can introduce its own local variables without affecting
variables and values in its outer scope(s).

It is required that subqueries be put inside parentheses `(` and `)` to
explicitly mark their start and end points:

```aql
FOR p IN persons
  LET recommendations = ( // subquery start
    FOR r IN recommendations
      FILTER p.id == r.personId
      SORT p.rank DESC
      LIMIT 10
      RETURN r
  ) // subquery end
  RETURN { person : p, recommendations : recommendations }
```

A subquery's result can be assigned to a variable with `LET` as shown
above, so that it can be referenced multiple times or just to improve
the query readability.

Function calls also use parentheses and AQL allows you to omit an extra
pair if you want to use a subquery as sole argument for a function, e.g.
`MAX(<subquery>)` instead of `MAX((<subquery>))`:

```aql
FOR p IN persons
  COLLECT city = p.city INTO g
  RETURN {
    city : city,
    numPersons : LENGTH(g),
    maxRating: MAX( // subquery start
      FOR r IN g
      RETURN r.p.rating
    ) // subquery end
  }
```

The extra wrapping is required if there is more than one function argument,
however, e.g. `NOT_NULL((RETURN "ok"), "fallback")`.

Subqueries may also include other subqueries.

Subqueries always return a result **array**, even if there is only
a single return value:

To unwind the result array of a subquery so that each element is returned as
top-level element in the overall query result, you can use a `FOR` loop:

```aql
FOR elem IN (RETURN 1..3) // [1,2,3]
  RETURN elem
```


### Graph traversals

A graph traversal is either a breadth-first or a depth-first search
starting from a single vertex.

Graph traversals are also done with a `FOR` statement, but with slightly
different syntax, of which there are two variants. Each such statements
runs one graph traversal for each incoming item and emits one item for
each step in the traversal.

The first one uses named graphs:

```aql
FOR vertex[, edge[, path]]
  IN [min[..max]]
  OUTBOUND|INBOUND|ANY startVertex
  GRAPH graphName
  [PRUNE [pruneVariable = ]pruneCondition]
  [OPTIONS options]
```

- `FOR`: emits up to three variables for each emitted item:
  - **vertex** (object): the current vertex in a traversal
  - **edge** (object, *optional*): the current edge in a traversal
  - **path** (object, *optional*): representation of the current path with
    two members:
    - `vertices`: an array of all vertices on this path
    - `edges`: an array of all edges on this path
- `IN` `min..max`: the minimal and maximal depth for the traversal:
  - **min** (number, *optional*): edges and vertices returned by this query
    start at the traversal depth of *min* (thus edges and vertices below it are
    not returned). If not specified, it defaults to 1. The minimal
    possible value is 0.
  - **max** (number, *optional*): up to *max* length paths are traversed.
    If omitted, *max* defaults to *min*. Thus only the vertices and edges in
    the range of *min* are returned. *max* cannot be specified without *min*.
- `OUTBOUND|INBOUND|ANY`: follow outgoing, incoming, or edges pointing in either
  direction in the traversal. Note that this can't be replaced by a bind parameter.
- **startVertex** (string\|object): a vertex where the traversal originates from.
  This can be specified in the form of an ID string or in the form of a document
  with the `_id` attribute. All other values lead to a warning and an empty
  result. If the specified document does not exist, the result is empty as well
  and there is no warning.
- `GRAPH` **graphName** (string): the name identifying the named graph.
  Its vertex and edge collections are looked up. Note that the graph name
  is like a regular string, hence it must be enclosed by quote marks, like
  `GRAPH "graphName"`.
- `PRUNE` **expression** (AQL expression, *optional*):
  An expression, like in a `FILTER` statement, which is evaluated in every step of
  the traversal, as early as possible. The semantics of this expression are as follows:
  - If the expression evaluates to `false`, the traversal continues on the current path.
  - If the expression evaluates to `true`, the traversal does not continue on the
    current path. However, the paths up to this point are considered as a result
    (they might still be post-filtered or ignored due to depth constraints).
    For example, a traversal over the graph `(A) -> (B) -> (C)` starting at `A`
    and pruning on `B` results in `(A)` and `(A) -> (B)` being valid paths,
    whereas `(A) -> (B) -> (C)` is not returned because it gets pruned on `B`.

  You can only use a single `PRUNE` clause per `FOR` traversal operation, but
  the prune expression can contain an arbitrary number of conditions using `AND`
  and `OR` statements for complex expressions. You can use the variables emitted
  by the `FOR` operation in the prune expression, as well as all variables
  defined before the traversal.

  You can optionally assign the prune expression to a variable like
  `PRUNE var = <expr>` to use the evaluated result elsewhere in the query,
  typically in a `FILTER` expression.

The second syntax uses collection sets rather than named graphs:

```aql
[WITH vertexCollection1[, vertexCollection2[, vertexCollectionN]]]
FOR vertex[, edge[, path]]
  IN [min[..max]]
  OUTBOUND|INBOUND|ANY startVertex
  edgeCollection1[, edgeCollection2[, edgeCollectionN]]
  [PRUNE [pruneVariable = ]pruneCondition]
  [OPTIONS options]
```

The `WITH` statement does not come immediately before the `FOR`
statement but must be given at the very beginning of the query.

- `WITH`: Declaration of collections.
  - `collections`: list of vertex collections that are involved in the
    traversal
- `edgeCollections` One or more edge collections to use for the
  traversal (instead of using a named graph with `GRAPH graphName`).
  Vertex collections are determined by the edges in the edge collections.

  You can override the default traversal direction by setting `OUTBOUND`,
  `INBOUND`, or `ANY` before any of the edge collections.

  If the same edge collection is specified multiple times, it behaves as
  if it were specified only once. Specifying the same edge collection is
  only allowed when the collections do not have conflicting traversal
  directions.

  Views cannot be used as edge collections.

IMPORTANT: Make sure that all vertex collections from which vertices
will occur during the graph traversals are listed in the `WITH`
statement at the beginning of the query. This is needed for the ArangoDB
cluster to be able to get access to the correct collections and the
query will otherwise fail!

You can optionally specify the following options to modify the execution of a
graph traversal. If you specify unknown options, query warnings are raised.

#### `order`

Specify which traversal algorithm to use (string):
- `"bfs"` – the traversal is executed breadth-first. The results first
  contain all vertices at depth 1, then all vertices at depth 2 and so on.
- `"dfs"` (default) – the traversal is executed depth-first. It
  first returns all paths from `min` depth to `max` depth for one vertex at
  depth 1, then for the next vertex at depth 1 and so on.
- `"weighted"` - the traversal is a weighted traversal. Paths are enumerated
  with increasing cost. Also see `weightAttribute` and `defaultWeight`.
  A returned path has an additional attribute `weight` containing the
  cost of the path after every step. The order of paths having the same
  cost is non-deterministic. Negative weights are not supported and
  abort the query with an error.

#### `uniqueVertices`

Ensure vertex uniqueness (string):

- `"path"` – it is guaranteed that there is no path returned with a
  duplicate vertex
- `"global"` – it is guaranteed that each vertex is visited at most
  once during the traversal, no matter how many paths lead from the start
  vertex to this one. If you start with a `min depth > 1` a vertex that
  was found before *min* depth might not be returned at all (it still
  might be part of a path). It is required to set `order: "bfs"` or
  `order: "weighted"` because with depth-first search the results would
  be unpredictable. Note: Using this configuration the result is not
  deterministic any more. If there are multiple paths from `startVertex`
  to `vertex`, one of those is picked. In case of a `weighted` traversal,
  the path with the lowest weight is picked, but in case of equal weights
  it is undefined which one is chosen.
- `"none"` (default) – no uniqueness check is applied on vertices

#### `uniqueEdges`

Ensure edge uniqueness (string):

- `"path"` (default) – it is guaranteed that there is no path returned with a
  duplicate edge
- `"none"` – no uniqueness check is applied on edges. Note:
  Using this configuration, the traversal follows edges in cycles.

#### `edgeCollections`

Restrict edge collections the traversal may visit (string\|array).

If omitted or an empty array is specified, then there are no restrictions.

- A string parameter is treated as the equivalent of an array with a single
  element.
- Each element of the array should be a string containing the name of an
  edge collection.

#### `vertexCollections`

Restrict vertex collections the traversal may visit (string\|array).

If omitted or an empty array is specified, then there are no restrictions.

- A string parameter is treated as the equivalent of an array with a single
  element.
- Each element of the array should be a string containing the name of a
  vertex collection.
- The starting vertex is always allowed, even if it does not belong to one
  of the collections specified by a restriction.

#### `parallelism`

Parallelize traversal execution (number).

If omitted or set to a value of `1`, the traversal execution is not
parallelized. If set to a value greater than `1`, then up to that many
worker threads can be used for concurrently executing the traversal. The
value is capped by the number of available cores on the target machine.

Parallelizing a traversal is normally useful when there are many inputs
(start vertices) that the nested traversal can work on concurrently.
This is often the case when a nested traversal is fed with several tens
of thousands of start vertices, which can then be distributed randomly
to worker threads for parallel execution.

#### `maxProjections`

Specifies the number of document attributes per `FOR` loop to be used as
projections (number). The default value is `5`.

The AQL optimizer automatically detects which document attributes
you access in traversal queries and optimizes the data loading. This
optimization is beneficial if you have large documents but only access a
few document attributes. The `maxProjections` option lets you tune when
to load individual attributes versus the whole document.

#### `indexHint`

You can provide index hints for traversals to let the optimizer prefer
the vertex-centric indexes.

This is useful for cases where the selectively estimate of the edge
index is higher than the ones for suitable vertex-centric indexes (and
thus they aren't picked automatically) but the vertex-centric indexes
are known to perform better.

The `indexHint` option expects an object in the following format:

`{ "<edgeColl>": { "<direction>": { "<level>": <index> } } }`

- `<edgeColl>`: The name of an edge collection for which the index hint
  shall be applied. Collection names are case-sensitive.
- `<direction>`: The direction for which to apply the index hint.
  Valid values are `inbound` and `outbound`, in lowercase.
  You can specify indexes for both directions.
- `<level>`: The level/depth for which the index should be applied. Valid
  values are the string `base` (to define the default index for all levels)
  and any stringified integer values greater or equal to zero.
  You can specify multiple levels.
- `<index>`: The name of an index as a string, or multiple index names as
  a list of strings in the order of preference. The optimizer uses the first
  suitable index.

Because collection names and levels/depths are used as object keys,
enclose them in quotes to avoid query parse errors.

Example:

```aql
FOR v, e, p IN 1..4 OUTBOUND startVertex edgeCollection
OPTIONS {
  indexHint: {
    "edgeCollection": {
      "outbound": {
        "base": ["edge"],
        "1": "myIndex1",
        "2": ["myIndex2", "myIndex1"],
        "3": "myIndex3",
      }
    }
  }
}
FILTER p.edges[1].foo == "bar" AND
        p.edges[2].foo == "bar" AND
        p.edges[2].baz == "qux"
```

Index hints for levels other than `base` are only considered if the
traversal actually uses a specific filter condition for the specified level.
In the above example, this is true for levels 1 and 2, but not for level 3.
Consequently, the index hint for level 3 is ignored here.

An expression like `FILTER p.edges[*].foo ALL == "bar"` cannot utilize the
indexes you specify for individual levels (level 1, level 2, etc.) but uses
the index for the `base` level.

The vertex-centric indexes you specify are only used if they are eligible
and the index hints for traversals cannot be forced.

#### `weightAttribute`

Specifies the name of an attribute that is used to look up the weight of
an edge (string).

If no attribute is specified or if it is not present in the edge
document then the `defaultWeight` is used.

The attribute value must not be negative.

Weighted traversals do not support negative weights. If a document
attribute (as specified by `weightAttribute`) with a negative value is
encountered during traversal, the query is aborted with an error.

#### `defaultWeight`

Specifies the default weight of an edge (number). The default value is `1`.

The value must not be negative.

Weighted traversals do not support negative weights. If `defaultWeight` is set
to a negative number, then the query is aborted with an error.

#### `useCache`

Whether to use the in-memory cache for edges. The default is `true`.

You can set this option to `false` to not make a large graph operation
pollute the edge cache.

For traversals with a list of edge collections you can optionally
specify the direction for some of the edge collections. Say for example
you have three edge collections `edges1`, `edges2` and `edges3`, where
in `edges2` the direction has no relevance but in `edges1` and `edges3`
the direction should be taken into account. In this case you can use
`OUTBOUND` as general traversal direction and `ANY` specifically for
`edges2` as follows:

```aql
FOR vertex IN OUTBOUND
  startVertex
  edges1, ANY edges2, edges3
```

All collections in the list that do not specify their own direction
use the direction defined after `IN`. This allows to use a different
direction for each collection in your traversal.


### Shortest path

On can also express various shortest path searches using a `FOR` statement.
All these shortest paths statements run one computation per input item.

Note that `SHORTEST_PATH` computes one shortest path and emits the steps
in it. See `K_SHORTEST_PATHS` for a way to compute multiple shortest paths
and emit one path at a time.

The syntax is:

```aql
FOR vertex[, edge]
  IN OUTBOUND|INBOUND|ANY SHORTEST_PATH
  startVertex TO targetVertex
  GRAPH graphName
  [OPTIONS options]
```

Note that it is **not** possible to give minimal and maximal depths
with this statement!

- `FOR`: Emits up to two variables:
  - `vertex` (object): The current vertex on the shortest path
  - `edge` (object, *optional*): The edge pointing to the vertex
- `IN` `OUTBOUND|INBOUND|ANY`: Defines in which direction edges are followed
  (outgoing, incoming, or both)
- `startVertex` `TO` `targetVertex` (both string\|object): The two
  vertices between which the shortest path is computed. This can be
  specified in the form of an ID string or in the form of a document
  with the attribute `_id`. All other values lead to a warning and an
  empty result. If one of the specified documents does not exist, the
  result is empty as well and there is no warning.
- `GRAPH` **graphName** (string): The name identifying the named graph.
  Its vertex and edge collections are looked up for the path search.
- `OPTIONS` **options** (object, *optional*):

Shortest Path traversals do not support negative weights. If a document
attribute (as specified by `weightAttribute`) with a negative value is
encountered during traversal, or if `defaultWeight` is set to a negative
number, then the query is aborted with an error.

Note that a shortest path statement produces one item per step in the
shortest path.

Alternatively, one can use with edge collection sets like this:

```aql
FOR vertex[, edge]
  IN OUTBOUND|INBOUND|ANY SHORTEST_PATH
  startVertex TO targetVertex
  edgeCollection1, ..., edgeCollectionN
  [OPTIONS options]
```

Do not forget to declare all occurring vertex collections using the `WITH`
statement at the beginning of the query.

Both statement variants allow for the following options:

#### `weightAttribute`

A top-level edge attribute that should be used to read the edge weight
(string).

If the attribute does not exist or is not numeric, the `defaultWeight`
is used instead.

The attribute value must not be negative.

#### `defaultWeight`

This value is used as fallback if there is no `weightAttribute` in the
edge document, or if it's not a number (number).

The value must not be negative. The default is `1`.

#### `useCache`

Whether to use the in-memory cache for edges. The default is `true`.

You can set this option to `false` to not make a large graph operation
pollute the edge cache.

As for normal traversals, for shortest path with a list of edge
collections you can optionally specify the direction for some of the
edge collections. Say for example you have three edge

The `SHORTEST_PATH` computation only finds an unconditioned shortest path.
With this construct it is not possible to define a condition like: "Find the
shortest path where all edges are of type *X*". If you want to do this, use a
normal traversal `{order: "bfs"}` in combination with `LIMIT 1`.

### Multiple shortest paths

The "K_SHORTEST_PATHS" type of query finds the first `k` paths in order
of length (or weight) between two given documents (`startVertex` and
`targetVertex`) in your graph.

If you need just one shortest path but want to get it as a single item,
use `K_SHORTEST_PATHS` and follow with `LIMIT 1`.

Every such path is returned as a JSON object with three components:

- an array containing the `vertices` on the path
- an array containing the `edges` on the path
- the `weight` of the path, that is the sum of all edge weights

If no `weightAttribute` is specified, the weight of the path is just its
length.

There are again two alternative ways for the syntax:

```aql
FOR path
  IN OUTBOUND|INBOUND|ANY K_SHORTEST_PATHS
  startVertex TO targetVertex
  GRAPH graphName
  [OPTIONS options]
  [LIMIT offset, count]
```

using a named graph and

```aql
FOR path
  IN OUTBOUND|INBOUND|ANY K_SHORTEST_PATHS
  startVertex TO targetVertex
  edgeCollection1, ..., edgeCollectionN
  [OPTIONS options]
  [LIMIT offset, count]
```

using an edge collection list. Do not forget to declare the vertex collection
in a `WITH` statement. The options are the same as for shortest path. When
giving an edge collection list one can override the direction for each
occurring edge collection in the list as before.

Very similar to this is the "k-paths" variant which has this syntax:

```aql
FOR path
  IN MIN..MAX OUTBOUND|INBOUND|ANY K_PATHS
  startVertex TO targetVertex
  GRAPH graphName
  [OPTIONS options]
```

it enumerates **all** paths from `startVertex` to `targetVertex` with
a length at least `MIN` and at most `MAX`.

The same can be done with an edge collection list:

```aql
FOR path
  IN MIN..MAX OUTBOUND|INBOUND|ANY K_PATHS
  startVertex TO targetVertex
  edgeCollection1, ..., edgeCollectionN
  [OPTIONS options]
```

Similarly, there is "all shortest paths" without a length limitation:

```aql
FOR path
  IN OUTBOUND|INBOUND|ANY ALL_SHORTEST_PATHS
  startVertex TO targetVertex
  GRAPH graphName
  [OPTIONS options]
```

for a named graph or

```aql
FOR path
  IN OUTBOUND|INBOUND|ANY ALL_SHORTEST_PATHS
  startVertex TO targetVertex
  edgeCollection1, ..., edgeCollectionN
```

for a list of edge collections.


### Geo queries

Geo location or GeoJSON objects can be stored and indexed with geo indexes.

AQL queries can make use of a geo index in the following ways:

```aql
FOR x IN geo_collection
  FILTER GEO_DISTANCE([@lng, @lat], x.geometry) <= 100000
```

or

```aql
FOR x IN geo_collection
  FILTER GEO_DISTANCE(@geojson, x.geometry) <= 100000
```

performs a "NEAR"-type query. The index will be used to find all documents
in the collection `geo_collection`, whose `geometry` attribute contains
a geo location which is closer than 100000 meters away from the given point.
The point can either be given as a longitude-latitude pair or as a
GeoJson object. Note that GeoJson specifies longitude first and latitude,
too.

The second type of geo query is the sorted "NEAR"-type query, which is
done as follows:

```aql
FOR x IN geo_collection
  SORT GEO_DISTANCE([@lng, @lat], x.geometry) ASC
  LIMIT 1000
```

This query returns the 1000 closest documents to a point, according to
their `geometry` attribute. The position can be either given as
longitude/latitude pair or as GeoJson object.

The third type of geo query is the one for a distance range:

```aql
FOR x IN geo_collection
  FILTER GEO_DISTANCE([@lng, @lat], x.geometry) <= 100000
  FILTER GEO_DISTANCE([@lng, @lat], x.geometry) >= 1000
```

This query delivers all documents from `geo_collection`, whose distance
to the given point is greater than or equal to 1000m and less than or equal
to 100000m.

Furthermore, containment in a geo polygon can be specified like this:

```aql
LET polygon = GEO_POLYGON([[[60,35],[50,5],[75,10],[70,35],[60,35]]])
FOR x IN geo_collection
  FILTER GEO_CONTAINS(polygon, x.geometry)
```

This delivers all documents, whose `geometry` attribute contains a GeoJson
object which is contained in the given polygon.

Finally, intersecting a given polygon is specified like this:

```aql
LET polygon = GEO_POLYGON([[[60,35],[50,5],[75,10],[70,35],[60,35]]])
FOR x IN geo_collection
  FILTER GEO_INTERSECTS(polygon, x.geometry)
  RETURN x
```

These `FILTER` clauses can be combined with a `SORT` clause using
`GEO_DISTANCE()`.


### Multi-dimensional queries

A multi-dimensional index maps multi-dimensional data in the form of
multiple numeric attributes to one dimension while mostly preserving
locality so that similar values in all of the dimensions remain close
to each other in the mapping to a single dimension. Queries that filter
by multiple value ranges at once can be better accelerated with such an
index compared to a persistent index.

You can choose between two subtypes of multi-dimensional indexes:

- An `mdi` index with a `fields` property that describes which document
  attributes to use as dimensions
- An `mdi-prefixed` index with a `fields` property as well as a
  `prefixFields` property to specify one or more mandatory document
  attributes to narrow down the search space using equality checks.

Both subtypes require that the attributes described by `fields` have
numeric values. You can optionally omit documents from the index that
have any of the `fields` or `prefixFields` attributes not set or set to
`null` by declaring the index as sparse with `sparse: true`.

You can store additional attributes in multi-dimensional indexes with
the `storedValues` property. They can be used for projections (unlike
the `fields` attributes) so that indexes can cover more queries without
having to access the full documents.

Example: Querying documents within a 3D box

Assume we have documents in a collection `points` of the form

```json
{"x": 12.9, "y": -284.0, "z": 0.02}
```

and we want to query all documents that are contained within a box defined by
`[x0, x1] * [y0, y1] * [z0, z1]`.

To do so one creates a multi-dimensional index on the attributes `x`, `y` and
`z`, e.g. in _arangosh_:

```js
db.points.ensureIndex({
  type: "mdi",
  fields: ["x", "y", "z"],
  fieldValueTypes: "double"
});
```

Unlike with other indexes, the order of the `fields` does not matter.

`fieldValueTypes` is required and the only allowed value is `"double"`
to use a double-precision (64-bit) floating-point format internally.

Now we can use the index in a query:

```aql
FOR p IN points
  FILTER x0 <= p.x && p.x <= x1
  FILTER y0 <= p.y && p.y <= y1
  FILTER z0 <= p.z && p.z <= z1
  RETURN p
```

Having an index on a set of fields does not require you to specify a
full range for every field. For each field you can decide if you want
to bound it from both sides, from one side only (i.e. only an upper or
lower bound) or not bound it at all.

Furthermore you can use any comparison operator. The index supports
`<=` and `>=` naturally, `==` will be translated to the bound `[c, c]`.
Strict comparison is translated to their non-strict counterparts and a
post-filter is inserted.

The `null` value is less than all other values in AQL. Therefore, range
queries without a lower bound need to include `null` but **sparse**
indexes do not include `null` values. For example, `FILTER p.x < 9` sets
an upper bound, but unless you also set a lower bound like `AND p.x >=
2`, the lower bound is basically `p.x >= null`.

You can explicitly exclude `null` in range queries so that sparse
indexes can be utilized: `FILTER p.x < 9 AND p.x != null`

If you build a calendar using ArangoDB you could create a collection for
each user that contains the appointments. The documents would roughly
look as follows:

```json
{
  "from": 345365,
  "to": 678934,
  "what": "Dentist",
}
```

`from`/`to` are the timestamps when an appointment starts/ends. Having
an multi-dimensional index on the fields `["from", "to"]` allows you to
query for all appointments within a given time range efficiently.

Given a time range `[f, t]` we want to find all appointments `[from,
to]` that are completely contained in `[f, t]`. Those appointments
clearly satisfy the condition

```
f <= from and to <= t
```

Thus our query would be:

```aql
FOR app IN appointments
  FILTER f <= app.from
  FILTER app.to <= t
  RETURN app
```

Given a time range `[f, t]` we want to find all appointments `[from,
to]` that intersect `[f, t]`. Two intervals `[f, t]` and `[from, to]`
intersect if and only if

```
f <= to and from <= t
```

Thus our query would be:

```aql
FOR app IN appointments
  FILTER f <= app.to
  FILTER app.from <= t
  RETURN app
```

#### Prefix fields

Multi-dimensional indexes can accelerate range queries well but they
are inefficient for queries that check for equality of values. For use
cases where you have a combination of equality and range conditions in
queries, you can use the `mdi-prefixed` subtype instead of `mdi`. It has
all the features of the `mdi` subtype but additionally lets you define
one or more document attributes you want to use for equality checks.
This combination allows to efficiently narrow down the search space to
a subset of multi-dimensional index data before performing the range
checking.

The attributes for equality checking are specified via the
`prefixFields` property of `mdi-prefix` indexes. These attributes can
have non-numeric values, unlike the attributes you use as `fields`.

```js
db.<collection>.ensureIndex({
  type: "mdi-prefixed",
  prefixFields: ["v", "w"]
  fields: ["x", "y"],
  fieldValueTypes: "double"
});
```

You need to specify all of the `prefixFields` attributes in your queries to
utilize the index.

```aql
FOR p IN points
  FILTER p.v == "type"
  FILTER p.w == "group"
  FILTER 2 <= p.x && p.x < 9
  FILTER p.y >= 80
  RETURN p
```

You can create `mdi-prefixed` indexes on edge collections with the
`_from` or `_to` edge attribute as the first prefix field. Graph
traversals with range filters can then utilize such indexes.

#### Storing additional values in indexes

Multi-dimensional indexes allow you to store additional attributes in
the index that can be used to satisfy projections of the document. They
cannot be used for index lookups or for sorting, but for projections
only. They allow multi-dimensional indexes to fully cover more queries
and avoid extra document lookups. This can have a great positive effect
on index scan performance if the number of scanned index entries is
large.

You can set the `storedValues` option and specify the additional
attributes as an array of attribute paths when creating a new `mdi` or
`mdi-prefixed` index, similar to the `fields` option:

```js
db.<collection>.ensureIndex({
  type: "mdi",
  fields: ["x", "y"],
  fieldValueTypes: "double",
  storedValues: ["y", "z"]
});
```

This indexes the `x` and `y` attributes so that the index can be used
for range queries by these attributes. Using these document attributes
like for returning them from the query is not covered by the index,
however, unless you add the attributes to `storedValues` in addition to
`fields`. The reason is that the index doesn't store the original values
of the attributes.

You can have the same attributes in `storedValues` and `fields` as the
attributes in `fields` cannot be used for projections, but you can also
store additional attributes that are not listed in `fields`. The above
example stores the `y` and `z` attribute values in the index using
`storedValues`. The index can thus supply the values for projections
without having to look up the full document.

Attributes in `storedValues` cannot overlap with the attributes
specified in `prefixFields`. There is no reason to store them in the
index because you need to specify them in queries in order to use
`mdi-prefixed` indexes.

In unique indexes, only the index attributes in `fields` and (for
`mdi-prefixed` indexes) `prefixFields` are checked for uniqueness. The
index attributes in `storedValues` are not checked for their uniqueness.

You cannot create multiple multi-dimensional indexes with the same
`sparse`, `unique`, `fields` and (for `mdi-prefixed` indexes)
`prefixFields` attributes but different `storedValues` settings. That
means the value of `storedValues` is not considered by index creation
calls when checking if an index is already present or needs to be
created.

Non-existing attributes are stored as `null` values.

The maximum number of attributes that you can use in `storedValues` is 32.

Using the lookahead index hint can increase the performance for certain use
cases. Specifying a lookahead value greater than zero makes the index fetch
more documents that are no longer in the search box, before seeking to the
next lookup position. Because the seek operation is computationally expensive,
probing more documents before seeking may reduce the number of seeks, if
matching documents are found. Please keep in mind that it might also affect
performance negatively if documents are fetched unnecessarily.

You can specify the `lookahead` value using the `OPTIONS` keyword:

```aql
FOR app IN appointments OPTIONS { lookahead: 32 }
    FILTER @to <= app.to
    FILTER app.from <= @from
    RETURN app
```

#### Limitations

- Using array expansions for attributes is not possible (e.g. `array[*].attr`)
- You can only index numeric values that are representable as IEEE-754 double.
- A high number of dimensions (more than 5) can impact the performance
  considerably.
- The performance can vary depending on the dataset. Densely packed
  points can lead to a high number of seeks. This behavior is typical for
  indexing using space filling curves.


### Array indexes

If an index attribute contains an array, ArangoDB will store the entire
array as the index value by default. Accessing individual members of the
array via the index is not possible this way.

To make an index insert the individual array members into the index
instead of the entire array value, a special array index needs to be
created for the attribute. Array indexes can be set up like regular
persistent indexes using the `collection.ensureIndex()` function. To
make a persistent index an array index, the index attribute name needs
to be extended with `[*]` when creating the index and when filtering in
an AQL query using the `IN` operator.

The following example creates an persistent array index on the `tags`
attribute in a collection named `posts`:

```js
db.posts.ensureIndex({ type: "persistent", fields: [ "tags[*]" ] });
db.posts.insert({ tags: [ "foobar", "baz", "quux" ] });
```

This array index can then be used for looking up individual `tags`
values from AQL queries via the `IN` operator:

```aql
FOR doc IN posts
  FILTER 'foobar' IN doc.tags
  RETURN doc
```

It is possible to add the array expansion operator `[*]`, but it is not
mandatory. You may use it to indicate that an array index is used, it is
purely cosmetic however:

```aql
FOR doc IN posts
  FILTER 'foobar' IN doc.tags[*]
  RETURN doc
```

The following FILTER conditions will **not use** the array index:

```aql
FILTER doc.tags ANY == 'foobar'
FILTER doc.tags ANY IN 'foobar'
FILTER doc.tags IN 'foobar'
FILTER doc.tags == 'foobar'
FILTER 'foobar' == doc.tags
```


### Modifying queries

You can use the `INSERT` statement to create new documents in a collection:

```aql
INSERT document INTO collection
```

It can optionally end with an `OPTIONS { … }` clause.

`collection` must contain the name of the collection into which the
documents should be inserted. `document` is the document to be inserted,
and it may or may not contain a `_key` attribute. If no `_key` attribute
is provided, ArangoDB will auto-generate a value for `_key` value.
Inserting a document will also auto-generate a document revision number
for the document.

The `INSERT` statement introduces a new variable `NEW` into the scope,
which will contain the newly inserted document including all attributes,
even those auto-generated by the database (e.g. `_id`, `_key`, `_rev`).

The `REPLACE` and `UPDATE` statements can be used to replace or update
documents in AQL using two different syntaxes:

```aql
REPLACE document IN collection
REPLACE keyExpression WITH document IN collection
```

similarly, `UPDATE` works as follows:

```aql
UPDATE document IN collection
UPDATE keyExpression WITH document IN collection
```

All variants can optionally end with an `OPTIONS { … }` clause.

In the first form, the document to be updated is determined by the `_key`
attribute of `document`. In the second form, the `keyExpression` must
evaluate to a string, which is the key of the document to modify.

In the `REPLACE` case, the complete document is replaced, for `UPDATE`,
`document` must be an object and contain the attributes and values to
update. **Attributes that don't yet exist** in the stored document **are
added** to it. **Existing attributes are set to the provided attribute
values** (excluding the immutable `_id` and `_key` attributes and the
system-managed `_rev` attribute). The operation leaves other existing
attributes not specified in `document` untouched.

Both statements introduce two new variables `NEW` and `OLD` into the scope,
which contain the new resp. old revision of the document.

The `REMOVE` statement can remove documents, there are again two syntax
possibilities:

```aql
REMOVE document IN collection
REMOVE keyExpression IN collection
```

The two variants behave similarly to above. A new variable `OLD` is
introduced into the scope by the `REMOVE` statement, containing the document
which was removed.

Finally, there is the `UPSERT` statement:

```aql
UPSERT searchExpression
  INSERT insertExpression
  UPDATE updateExpression
  IN collection
```

The syntax for a repsert operation:

```aql
UPSERT searchExpression
  INSERT insertExpression
  REPLACE replaceExpression
  IN collection
```

Both variants can optionally end with an `OPTIONS { … }` clause.

As before, the `searchExpression` can either evaluate to an object with
a `_key` attribute or to a string. The `insertExpression` is used if no
document with the specified `_key` exists, the `updateExpression`
or `replaceExpression` is used if such a document exists.

The following options exist for modifying queries:

 - `ignoreErrors` (boolean): suppresses query errors (for example unique
   constraints) and lets the query continue in this case

 - `waitForSync` (boolean): let's query completion wait until every
   change is synced to durable storage

 - `overwriteMode` (only for `INSERT`): the following string values are
   possible:

   - `"ignore"`: if a document with the specified `_key` value exists
     already, nothing will be done and no write operation will be carried
     out. The insert operation will return success in this case. This mode
     does not support returning the old document version. Using `RETURN
     OLD` will trigger a parse error, as there will be no old version to
     return. `RETURN NEW` will only return the document in case it was
     inserted. In case the document already existed, `RETURN NEW` will
     return `null`.
    - `"replace"`: if a document with the specified `_key` value exists
      already, it will be overwritten with the specified document value.
      This mode will also be used when no overwrite mode is specified but
      the `overwrite` flag is set to `true`.
    - `"update"`: if a document with the specified `_key` value exists
      already, it will be patched (partially updated) with the specified
      document value.
    - `"conflict"`: if a document with the specified `_key` value exists
      already, return a unique constraint violation error so that the
      insert operation fails. This is also the default behavior in case
      the overwrite mode is not set, and the `overwrite` flag is `false`
      or not set either.

   The main use case of inserting documents with overwrite mode `ignore`
   is to make sure that certain documents exist in the cheapest possible
   way. In case the target document already exists, the `ignore` mode is
   most efficient, as it will not retrieve the existing document from
   storage and not write any updates to it.

   When using the `update` overwrite mode, the `keepNull` and
   `mergeObjects` options control how the update is done.

 - `exclusive` (boolean): this option will request an exclusive lock on the
   collection

 - `refillIndexCachges` (boolean): if this option is given, new entries
   will automatically be added to the in-memory index caches, if the
   edge-index or cache-enabled persistent indexes are affected.

 - `versionAttribute` (string): You can use the `versionAttribute`
   option for external versioning support. If set, the attribute with
   the name specified by the option is looked up in the stored document
   and the attribute value is compared numerically to the value of the
   versioning attribute in the supplied document that is supposed to
   update/replace it.

   If the version number in the new document is higher (rounded down
   to a whole number) than in the document that already exists in the
   database, then the update/replace operation is performed normally.

   This is also the case if the new versioning attribute has a
   non-numeric value, if it is a negative number, or if the attribute
   doesn't exist in the supplied or stored document.

   If the version number in the new document is lower or equal to what
   exists in the database, the operation is not performed and the
   existing document thus not changed. No error is returned in this
   case.

   The attribute can only be a top-level attribute.

 - `ignoreRevs` (boolean, only `REPLACE`, `UPDATE` and `UPSERT`):
   if this is set, ArangoDB will compare the `_rev` value and only succeeed
   if they still match. The default is `false`. This can be used to not
   accidentally overwrite documents that have been modified since you
   last fetched them.

 - `keepNull` (boolean, only `UPDATE` and `UPSERT`): When updating an
   attribute to the `null` value, ArangoDB does not remove the attribute
   from the document but stores this `null` value. To remove attributes in
   an update operation, set them to `null` and set the `keepNull` option to
   `false`. This removes the attributes you specify but not any previously
   stored attributes with the `null` value:

 - `mergeObjects` (boolean, only `UPDATE` and `UPSERT`):
   the option `mergeObjects` controls whether object contents are merged
   if an object attribute is present in both the `UPDATE` query and in the
   to-be-updated document.


### Search queries

Search queries are only possible if a search view or search-alias view
exists. Note that search views must be linked to a collection by means of
a "link" and search-alias views must be linked to a collection by means
of an "inverted index" on the collection.

In either case, the syntax is:

```aql
FOR doc IN viewName
  SEARCH searchexpression
  OPTIONS { ... }
```

where `viewName` is the name of a search view or search-alias view and
`searchexpression` is an ArangoSearch expression to specify what to
search for.

In general, this searchexpression has to specify two things:
 - the way data is "analyzed" both when building the index as well as
   when querying it
 - the actual search condition

This is, where the pseudo-function `ANALYZER` comes in. For example,
the searchexpression

```aql
FOR doc IN view
  SEARCH ANALYZER(doc.keywords == "dog", "text_en")
  RETURN doc
```

means that we are using the `text_en` analyzer, which tokenizes the
indexed field into individual words. Therefore, the condition
`doc.keywords == "dog"` is interpreted in this way and the document is
a match if **one of the tokens** the field contains is `dog`.

If the `ANALYZER` pseudo function call is left out, the default `identity`
analyzer is used and the condition is only about **complete equality**
of the field with the string `"dog"`!

Obviously, to use the analyzer `text_en` the field has to be indexed
with this analyzer, so the search index definition needs the information
about the analyzer, too.

Logical or Boolean operators allow you to combine multiple search conditions.

- `AND`, `&&` (conjunction)
- `OR`, `||` (disjunction)
- `NOT`, `!` (negation / inversion)

The following comparison operators can be used in searchexpressions:

- `==` (equal)
- `<=` (less than or equal)
- `>=` (greater than or equal)
- `<` (less than)
- `>` (greater than)
- `!=` (unequal)
- `IN` (contained in array or range), also `NOT IN`
- `LIKE` (equal with wildcards), also `NOT LIKE`

Array comparison operators can be used as seen in the following queries:

```aql
LET tokens = TOKENS("some input", "text_en")                 // ["some", "input"]
FOR doc IN myView SEARCH tokens  ALL IN doc.text RETURN doc // dynamic conjunction
FOR doc IN myView SEARCH tokens  ANY IN doc.text RETURN doc // dynamic disjunction
FOR doc IN myView SEARCH tokens NONE IN doc.text RETURN doc // dynamic negation
FOR doc IN myView SEARCH tokens  ALL >  doc.text RETURN doc // dynamic conjunction with comparison
FOR doc IN myView SEARCH tokens  ANY <= doc.text RETURN doc // dynamic disjunction with comparison
FOR doc IN myView SEARCH tokens NONE <  doc.text RETURN doc // dynamic negation with comparison
FOR doc IN myView SEARCH tokens AT LEAST (1+1) IN doc.text RETURN doc // dynamically test for a subset of elements
```

Note how the `TOKENS` function is used to cut a string into its tokens
using an analyzer.

The following operators are equivalent in `SEARCH` expressions:
- `ALL IN`, `ALL ==`, `NONE !=`, `NONE NOT IN`
- `ANY IN`, `ANY ==`
- `NONE IN`, `NONE ==`, `ALL !=`, `ALL NOT IN`
- `ALL >`, `NONE <=`
- `ALL >=`, `NONE <`
- `ALL <`, `NONE >=`
- `ALL <=`, `NONE >`
- `AT LEAST (...) IN`, `AT LEAST (...) ==`
- `AT LEAST (1) IN`, `ANY IN`

You can use the question mark operator to perform nested searches with
ArangoSearch:

```aql
FOR doc IN myView
  SEARCH doc.dimensions[? FILTER CURRENT.type == "height" AND CURRENT.value > 40]
  RETURN doc
```

It allows you to match nested objects in arrays that satisfy multiple
conditions each, and optionally define how often these conditions should
be fulfilled for the entire array. You need to configure the View
specifically for this type of search using the `nested` property in
`arangosearch` views or in the definition of inverted indexes that you
can add to search-alias views.

Document attributes which are not configured to be indexed by a View are
treated by `SEARCH` as non-existent. This affects tests against the documents
emitted from the View only.

The documents emitted from a View can be sorted by attribute values with
the standard `SORT` statement, using one or multiple attributes, in
ascending or descending order (or a mix thereof).

```aql
FOR doc IN viewName
  SORT doc.text, doc.value DESC
  RETURN doc
```

If the (left-most) fields and their sorting directions match up with the
primary sort order definition of the View then the `SORT` operation is
optimized away.

Apart from simple sorting, it is possible to sort the matched View
documents by relevance score (or a combination of score and attribute
values if desired). The document search via the `SEARCH` keyword and
the sorting via the ArangoSearch scoring functions, namely `BM25` and
`TFIDF`, are closely intertwined. The query given in the `SEARCH`
expression is not only used to filter documents, but also is used with
the scoring functions to decide which document matches the query best.
Other documents in the View also affect this decision.

Therefore the ArangoSearch scoring functions can work **only** on
documents emitted from a View, as both the corresponding `SEARCH`
expression and the View itself are consulted in order to sort the
results.

```aql
FOR doc IN viewName
  SEARCH ...
  SORT BM25(doc) DESC
  RETURN doc
```

The `BOOST` can be used to fine-tune the resulting ranking by weighing
sub-expressions in `SEARCH` differently.

#### Search options

The following options can be used in the `OPTIONS` part of a search
expression:

 - `collections`: You can specify an array of strings with collection
   names to restrict the search to certain source collections.
 - `conditionOptimization`: You can specify one of the following values
   for this option to control how search criteria get optimized:

    - `"auto"` (default): convert conditions to disjunctive normal form
      (DNF) and apply optimizations. Removes redundant or overlapping
      conditions, but can take quite some time even for a low number of
      nested conditions.
    - `"none"`: search the index without optimizing the conditions.

 - `countApproximate`: This option controls how the total count of rows
   is calculated if the `fullCount` option is enabled for a query or when
   a `COLLECT WITH COUNT` clause is executed. You can set it to one of the
   following values:

    - `"exact"` (default): rows are actually enumerated for a precise count.
    - `"cost"`: a cost-based approximation is used. Does not enumerate
      rows and returns an approximate result with O(1) complexity. Gives a
      precise result if the `SEARCH` condition is empty or if it contains
      a single term query only (e.g. `SEARCH doc.field == "value"`), the
      usual eventual consistency of Views aside.

 - `parallelism`: A `SEARCH` operation can optionally process index
   segments in parallel using multiple threads. This can speed up search
   queries but increases CPU and memory utilization.


#### Analyzers

The following Analyzer types are available:

- `identity`: treats value as atom (no transformation)
- `delimiter`: splits into tokens at a user-defined character sequence
- `multi_delimiter`: splits into tokens at user-defined character sequences
- `stem`: applies stemming to the value as a whole
- `norm`: applies normalization to the value as a whole
- `ngram`: creates _n_-grams from the value with user-defined lengths
- `text`: tokenizes text strings into words, optionally with stemming,
  normalization, stop-word filtering and edge _n_-gram generation
- `segmentation`: tokenizes text in a language-agnostic manner,
  optionally with normalization
- `wildcard`: can apply another Analyzer and creates _n_-grams to
  enable fast partial matching for large strings
- `aql`: runs an AQL query to prepare tokens for index
- `pipeline`: chains multiple Analyzers
- `stopwords`: removes the specified tokens from the input
- `collation`: respects the alphabetic order of a language in range queries
- `minhash`: applies another Analyzer and then a locality-sensitive
  hash function, to find candidates for set comparisons based on the
  Jaccard index
- `classification`: classifies the input text using a word embedding model
- `nearest_neighbors`: finds tokens similar to the ones
  in the input text using a word embedding model
- `geojson`: breaks up a GeoJSON object into a set of indexable tokens
- `geo_s2`: like `geojson` but offers more efficient formats for
  indexing geo-spatial data
- `geopoint`: breaks up JSON data describing a coordinate pair into
  a set of indexable tokens

The following table compares the Analyzers for **text processing**:

Analyzer  /  Capability                   | Tokenization | Stemming | Normalization | _N_-grams
:----------------------------------------:|:------------:|:--------:|:-------------:|:--------:
[`stem`](#stem)                           |      No      |   Yes    |      No       |   No
[`norm`](#norm)                           |      No      |    No    |     Yes       |   No
[`ngram`](#ngram)                         |      No      |    No    |      No       |  Yes
[`text`](#text)                           |     Yes      |   Yes    |     Yes       | (Yes)
[`segmentation`](#segmentation)           |     Yes      |    No    |     Yes       |   No


## General instructions for all queries

IMPORTANT: Make sure that all vertex collections from which vertices
will occur during the graph traversals are listed in the `WITH`
statement at the beginning of the query. This is needed for the ArangoDB
cluster to be able to get access to the correct collections and the
query will otherwise fail!

# EXTREMELY IMPORTANT INFORMATION

You will fail if you don't follow the following final instructions.

1. Always use the `WITH` statement at the very beginning of the query.
2. Always use a graph traversal to find the vertices and edges that are connected to the vertices if possible.
3. Graph traversals are the way to go. This is not SQL.
4. Don't write queries without the`WITH` statement at the very beginning of the query.
5. If your query isn't working out, make sure you have the `WITH` statement at the very beginning of the query and you're doing a graph traversal if feasible. You can re-read the instructions on graph traversals at any time.
