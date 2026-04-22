#include <iostream>
using namespace std;

int main() {
    int a;
    int b;
    cin >> a >> b;

    int sum = a + b;
    cout << "Sum: " << sum << endl;

    int limit = 10;
    while (a < limit) {
        a = a + 1;
        if (a == 5) {
            continue;
        }
    }

    cout << "Final a: " << a << endl;
    return 0;
}
